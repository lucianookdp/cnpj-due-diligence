import { useNavigate } from "react-router-dom";
import { AuthForm } from "../components/AuthForm";

interface LoginPageProps {
  onAuthenticated: () => void;
}

export function LoginPage({ onAuthenticated }: LoginPageProps) {
  const navigate = useNavigate();

  return (
    <div className="auth-page">
      <AuthForm
        onAuthenticated={() => {
          onAuthenticated();
          navigate("/");
        }}
      />
    </div>
  );
}
