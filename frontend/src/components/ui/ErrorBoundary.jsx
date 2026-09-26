import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught error:', error, errorInfo);
  }

  reset = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'var(--color-bg, #04231b)',
            padding: 24,
            fontFamily: 'Inter, system-ui, sans-serif',
            color: '#fff',
          }}
        >
          <div
            style={{
              background: 'rgba(255, 255, 255, 0.08)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              borderRadius: 16,
              padding: '36px 32px',
              maxWidth: 480,
              width: '100%',
              textAlign: 'center',
              boxShadow: '0 20px 40px rgba(0,0,0,0.4)',
            }}
          >
            <img
              src="/assets/logo.png"
              alt="Gabstep"
              style={{ width: 44, height: 44, margin: '0 auto 16px', display: 'block' }}
            />
            <h2
              style={{
                fontSize: '1.35rem',
                fontWeight: 600,
                margin: '0 0 8px',
                color: '#fff',
              }}
            >
              Application Portal Notice
            </h2>
            <p
              style={{
                fontSize: '0.9rem',
                color: 'rgba(255,255,255,0.7)',
                lineHeight: 1.5,
                margin: '0 0 24px',
              }}
            >
              We encountered an issue loading this section. Please reload the page or return to the main site.
            </p>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
              <button
                type="button"
                onClick={this.reset}
                style={{
                  background: '#0b5c43',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 8,
                  padding: '10px 18px',
                  fontWeight: 600,
                  fontSize: '0.875rem',
                  cursor: 'pointer',
                }}
              >
                Reload page
              </button>
              <a
                href="/"
                style={{
                  background: 'rgba(255,255,255,0.12)',
                  color: '#fff',
                  borderRadius: 8,
                  padding: '10px 18px',
                  fontWeight: 500,
                  fontSize: '0.875rem',
                  textDecoration: 'none',
                }}
              >
                Return to home
              </a>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
