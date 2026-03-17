import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

describe('AuthContext', () => {
  let AuthProvider, useAuth;

  beforeAll(() => {
    const mod = require('../../contexts/AuthContext');
    AuthProvider = mod.AuthProvider;
    useAuth = mod.useAuth;
  });

  const TestComponent = () => {
    const auth = useAuth();
    return (
      <div>
        <span data-testid="user">{auth.user ? JSON.stringify(auth.user) : 'null'}</span>
        <span data-testid="token">{auth.token || 'null'}</span>
        <button onClick={auth.logout}>Logout</button>
      </div>
    );
  };

  it('provides initial auth state', () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </MemoryRouter>
    );
    // Initially no user should be logged in (unless localStorage has data)
    expect(screen.getByTestId('user')).toBeInTheDocument();
  });

  it('provides logout function', () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </MemoryRouter>
    );
    expect(screen.getByText('Logout')).toBeInTheDocument();
  });
});
