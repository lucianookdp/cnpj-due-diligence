import { useState } from "react";
import { ApiRequestError, login, register, setToken } from "../api/client";

interface AuthFormProps {
  onAuthenticated: () => void;
}

export function AuthForm({ onAuthenticated }: AuthFormProps) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = mode === "login" ? await login(email, password) : await register(email, password);
      setToken(result.access_token);
      onAuthenticated();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Falha na autenticação");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card auth-card">
      <h2>{mode === "login" ? "Entrar" : "Criar conta"}</h2>
      <form onSubmit={handleSubmit} className="field-group">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="E-mail"
          required
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Senha"
          required
          minLength={6}
        />
        {error && <p className="text-sm" style={{ color: "var(--color-danger)", margin: 0 }}>{error}</p>}
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? "Aguarde..." : mode === "login" ? "Entrar" : "Criar conta"}
        </button>
      </form>
      <button
        type="button"
        className="btn-ghost"
        onClick={() => setMode(mode === "login" ? "register" : "login")}
        style={{ marginTop: "var(--space-2)" }}
      >
        {mode === "login" ? "Não tem conta? Criar uma" : "Já tem conta? Entrar"}
      </button>
    </div>
  );
}
