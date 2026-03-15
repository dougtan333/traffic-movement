/**
 * CitySelector — toggle between Sydney and Melbourne.
 *
 * @param {{ city: string, onChange: (city: string) => void }} props
 */
import './CitySelector.css';

export default function CitySelector({ city, onChange }) {
  return (
    <div className="city-selector">
      <button
        className={`city-btn ${city === 'sydney' ? 'active sydney' : ''}`}
        onClick={() => onChange('sydney')}
      >
        Sydney
      </button>
      <button
        className={`city-btn ${city === 'melbourne' ? 'active melbourne' : ''}`}
        onClick={() => onChange('melbourne')}
      >
        Melbourne
      </button>
    </div>
  );
}
