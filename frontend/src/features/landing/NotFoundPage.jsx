import { Link } from 'react-router-dom';
import SiteHeader from '../../components/layout/SiteHeader';
import Icon from '../../lib/icons';

export default function NotFoundPage() {
  return (
    <>
      <SiteHeader />
      <main className="marketing">
        <section className="section">
          <div className="container">
            <div className="section-head">
              <span className="section-eyebrow">Error 404</span>
              <h1 className="section-title">That page has moved on</h1>
              <p className="section-lede">
                The link may be out of date. Head back and pick up where you left off.
              </p>
            </div>
            <Link to="/" className="btn btn-primary btn-lg">
              <Icon name="home" size={18} strokeWidth={2} />
              Back to the start
            </Link>
          </div>
        </section>
      </main>
    </>
  );
}
