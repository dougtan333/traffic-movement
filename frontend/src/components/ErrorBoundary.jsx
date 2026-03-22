/**
 * ErrorBoundary — catches unhandled React errors and shows a fallback
 * instead of a white screen. Wraps the entire <App>.
 */
import { Component } from 'react';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info?.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '2rem', maxWidth: '600px', margin: '4rem auto',
          fontFamily: 'system-ui, sans-serif', textAlign: 'center',
        }}>
          <h2 style={{ marginBottom: '1rem' }}>Something went wrong</h2>
          <p style={{ color: '#666', marginBottom: '1.5rem' }}>
            The dashboard encountered an error. Try refreshing the page.
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '0.5rem 1.5rem', border: '1px solid #ccc',
              borderRadius: '6px', background: '#fff', cursor: 'pointer',
            }}
          >
            Refresh
          </button>
          {this.state.error && (
            <pre style={{
              marginTop: '1.5rem', padding: '1rem', background: '#f5f5f5',
              borderRadius: '6px', fontSize: '12px', textAlign: 'left',
              overflow: 'auto', maxHeight: '200px',
            }}>
              {this.state.error.toString()}
            </pre>
          )}
        </div>
      );
    }
    return this.props.children;
  }
}
