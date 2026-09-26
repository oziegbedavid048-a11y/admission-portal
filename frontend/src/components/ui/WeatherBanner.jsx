import { useMemo } from 'react';
import Icon from '../../lib/icons';
import { greetingFor } from '../../lib/format';

export default function WeatherBanner({ userName = '', subtitle = '', badge = null }) {
  const greeting = useMemo(() => greetingFor(), []);

  return (
    <section
      className={`weather-banner weather-banner-${greeting.period}`}
      style={{ backgroundImage: `url('${greeting.image}')` }}
      aria-label={`${greeting.text}, ${userName}`}
    >
      <div className="weather-banner-overlay" />
      <div className="weather-banner-body">
        <div className="weather-banner-left">
          <div className="weather-banner-icon-box" title={greeting.label}>
            <Icon name={greeting.icon} size={24} strokeWidth={2.2} />
          </div>
          <div className="weather-banner-text">
            <h2>
              {greeting.text}{userName ? `, ${userName}` : ''}
            </h2>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
        </div>

        {badge ? <div className="weather-banner-badge">{badge}</div> : null}
      </div>
    </section>
  );
}
