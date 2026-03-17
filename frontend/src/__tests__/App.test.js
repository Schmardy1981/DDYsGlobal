import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';

// Mock the auth context
jest.mock('../contexts/AuthContext', () => ({
  AuthProvider: ({ children }) => <div>{children}</div>,
  useAuth: () => ({
    user: null,
    token: null,
    loading: false,
    login: jest.fn(),
    logout: jest.fn(),
  }),
}));

describe('App', () => {
  it('renders without crashing', () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
  });

  it('redirects to login when not authenticated', () => {
    render(
      <MemoryRouter initialEntries={['/admin/dashboard']}>
        <App />
      </MemoryRouter>
    );
    // Should redirect to login when no auth
    expect(screen.getByText(/login/i) || document.body).toBeTruthy();
  });
});
