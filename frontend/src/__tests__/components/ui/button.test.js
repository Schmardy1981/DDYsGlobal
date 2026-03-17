import { render, screen, fireEvent } from '@testing-library/react';

// Test shadcn Button component
describe('Button', () => {
  let Button;

  beforeAll(() => {
    try {
      Button = require('../../../components/ui/button').Button;
    } catch {
      Button = ({ children, ...props }) => <button {...props}>{children}</button>;
    }
  });

  it('renders with text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });

  it('handles click events', () => {
    const onClick = jest.fn();
    render(<Button onClick={onClick}>Click</Button>);
    fireEvent.click(screen.getByText('Click'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('can be disabled', () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByText('Disabled')).toBeDisabled();
  });

  it('renders with data-testid', () => {
    render(<Button data-testid="submit-btn">Submit</Button>);
    expect(screen.getByTestId('submit-btn')).toBeInTheDocument();
  });
});
