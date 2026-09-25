"""PGFN federal-debt ("dívida ativa da União") open data, reduced to one line
per company. Standard library only: GitHub Actions runs `build` without
installing the app, so the multi-gigabyte download never touches the API
server — the server only receives the small summary (see
.github/workflows/pgfn-refresh.yml and the /internal/pgfn endpoints).

Usage: python -m app.pgfn_file build --out summary.csv.gz [--min-reais 100000] [--skip-if REF]
"""

import argparse
import csv
import gzip
import io
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path

BASE_URL = "https://dadosabertos.pgfn.gov.br"
FILES = ("Dados_abertos_Nao_Previdenciario", "Dados_abertos_Previdenciario", "Dados_abertos_FGTS")
USER_AGENT = "cnpj-due-diligence (+https://github.com/lucianookdp/cnpj-due-diligence)"
SUMMARY_HEADER = ["cnpj_root", "amount_cents", "inscriptions", "judicial"]


def quarter_candidates(now: datetime) -> list[str]:
    """Newest first: "2026_trimestre_03", "2026_trimestre_02", ... two years back."""
    year, quarter = now.year, (now.month - 1) // 3 + 1
    out = []
    for _ in range(8):
        out.append(f"{year}_trimestre_{quarter:02d}")
        quarter -= 1
        if quarter == 0:
            year, quarter = year - 1, 4
    return out


def _exists(url: str) -> bool:
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status == 200
    except OSError:
        return False


def latest_reference(now: datetime | None = None) -> str | None:
    """The newest quarter for which every file is published."""
    for reference in quarter_candidates(now or datetime.now(UTC)):
        if all(_exists(f"{BASE_URL}/{reference}/{name}.zip") for name in FILES):
            return reference
    return None


def _rows(zip_path: Path) -> Iterator[dict[str, str]]:
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if not info.filename.lower().endswith(".csv"):
                continue
            with archive.open(info) as raw:
                yield from csv.DictReader(
                    io.TextIOWrapper(raw, encoding="latin-1", newline=""), delimiter=";"
                )


def aggregate(rows: Iterable[dict[str, str]]) -> dict[str, list]:
    """Company root (first 8 CNPJ digits) -> [cents, inscriptions, judicial].

    Only debts the company itself owes ("Principal") that are actively being
    collected ("Em cobrança"): installment plans, guarantees and court
    suspensions are the company dealing with its debt, not evading it. People
    (CPFs) are skipped entirely.
    """
    totals: dict[str, list] = {}
    for row in rows:
        # Case differs between PGFN's own files ("Principal" in FGTS and
        # Previdenciário, "PRINCIPAL" in Não Previdenciário), so compare folded.
        if not row.get("TIPO_PESSOA", "").casefold().startswith("pessoa jur"):
            continue
        if (
            row.get("TIPO_DEVEDOR", "").casefold() != "principal"
            or row.get("TIPO_SITUACAO_INSCRICAO", "").casefold() != "em cobrança"
        ):
            continue
        digits = "".join(c for c in row.get("CPF_CNPJ", "") if c.isdigit())
        if len(digits) != 14:
            continue
        try:
            cents = round(float(row.get("VALOR_CONSOLIDADO") or 0) * 100)
        except ValueError:
            continue
        entry = totals.setdefault(digits[:8], [0, 0, False])
        entry[0] += cents
        entry[1] += 1
        entry[2] = entry[2] or row.get("INDICADOR_AJUIZADO", "").upper() == "SIM"
    return totals


def write_summary(totals: dict[str, list], reference: str, min_cents: int, out: Path) -> int:
    written = 0
    with gzip.open(out, "wt", encoding="utf-8", newline="") as fh:
        fh.write(f"# {reference}\n")
        writer = csv.writer(fh)
        writer.writerow(SUMMARY_HEADER)
        for root, (cents, count, judicial) in sorted(totals.items()):
            if cents >= min_cents:
                writer.writerow([root, cents, count, int(judicial)])
                written += 1
    return written


def build(out: Path, min_reais: int, skip_if: str | None) -> int:
    reference = latest_reference()
    if reference is None:
        print("no complete PGFN quarter found", file=sys.stderr)
        return 1
    if reference == skip_if:
        print(f"{reference} already imported, nothing to do")
        return 0

    totals: dict[str, list] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name in FILES:
            path = Path(tmp) / f"{name}.zip"
            request = urllib.request.Request(
                f"{BASE_URL}/{reference}/{name}.zip", headers={"User-Agent": USER_AGENT}
            )
            with urllib.request.urlopen(request, timeout=600) as response, open(path, "wb") as fh:
                shutil.copyfileobj(response, fh, length=1 << 20)
            for root, (cents, count, judicial) in aggregate(_rows(path)).items():
                entry = totals.setdefault(root, [0, 0, False])
                entry[0] += cents
                entry[1] += count
                entry[2] = entry[2] or judicial
            path.unlink()
            print(f"{name}: {len(totals)} companies so far", file=sys.stderr)

    written = write_summary(totals, reference, min_reais * 100, out)
    print(f"{reference}: {written} companies with at least R$ {min_reais} in collection -> {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    build_cmd = sub.add_parser("build")
    build_cmd.add_argument("--out", type=Path, required=True)
    build_cmd.add_argument("--min-reais", type=int, default=100_000)
    build_cmd.add_argument("--skip-if", default=None, help="reference already imported")
    args = parser.parse_args()
    return build(args.out, args.min_reais, args.skip_if)


if __name__ == "__main__":
    sys.exit(main())
