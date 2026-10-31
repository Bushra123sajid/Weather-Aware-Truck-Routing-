import logo from '../assets/logo.svg';

export function AppHeader() {
  return (
    <header className="app-header">
      <img src={logo} alt="RouteWise" className="app-header__logo" />
      <span className="app-header__tagline">Weather-aware truck routing</span>
    </header>
  );
}
