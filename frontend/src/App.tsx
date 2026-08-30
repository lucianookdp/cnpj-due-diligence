import { useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";
import "./App.css";
import { clearToken, getToken } from "./api/client";
import { Header } from "./components/Header";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";

type Theme = "light" | "dark";

function getInitialTheme(): Theme {
  const stored = localStorage.getItem("theme");
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function App() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  const [authenticated, setAuthenticated] = useState(() => getToken() !== null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
    window.dispatchEvent(new Event("themechange"));
  }, [theme]);

  function toggleTheme() {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
  }

  function handleLogout() {
    clearToken();
    setAuthenticated(false);
  }

  return (
    <div className="app-shell">
      <Header
        authenticated={authenticated}
        theme={theme}
        onToggleTheme={toggleTheme}
        onLogout={handleLogout}
      />
      <Routes>
        <Route path="/" element={<HomePage authenticated={authenticated} />} />
        <Route
          path="/login"
          element={<LoginPage onAuthenticated={() => setAuthenticated(true)} />}
        />
      </Routes>
    </div>
  );
}

export default App;
