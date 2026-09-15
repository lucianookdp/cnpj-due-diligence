import { Link } from "react-router-dom";
import { Icon } from "./Icon";

interface HeaderProps {
  authenticated: boolean;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onLogout: () => void;
}

export function Header({ authenticated, theme, onToggleTheme, onLogout }: HeaderProps) {
  return (
    <div className="app-header">
      <div className="app-brand">
        <span className="app-logo">
          <Icon name="radar" size={26} />
        </span>
        <div>
          <h1>Radar CNPJ</h1>
          <p className="app-header-tagline">Due diligence de empresas brasileiras</p>
        </div>
      </div>
      <div className="app-header-actions">
        {authenticated ? (
          <button type="button" className="btn-sm btn-with-icon" onClick={onLogout}>
            <Icon name="log-out" size={15} />
            Sair
          </button>
        ) : (
          <Link to="/login" className="btn-sm btn-with-icon">
            <Icon name="log-in" size={15} />
            Entrar
          </Link>
        )}
        <button
          type="button"
          className="btn-icon theme-toggle"
          onClick={onToggleTheme}
          aria-label={theme === "dark" ? "Ativar modo claro" : "Ativar modo escuro"}
          title={theme === "dark" ? "Ativar modo claro" : "Ativar modo escuro"}
        >
          <span key={theme} className="icon-pop-in">
            <Icon name={theme === "dark" ? "sun" : "moon"} size={17} />
          </span>
        </button>
      </div>
    </div>
  );
}
