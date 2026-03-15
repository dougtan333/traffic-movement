/**
 * TabNav — horizontal tab bar for dashboard sections.
 * Sits below the header, above the content.
 *
 * @param {{ tabs: Array<{id: string, label: string}>, active: string, onChange: (id: string) => void }} props
 */
import './TabNav.css';

export default function TabNav({ tabs, active, onChange }) {
  return (
    <nav className="tab-nav">
      {tabs.map(tab => (
        <button
          key={tab.id}
          className={`tab-btn ${active === tab.id ? 'active' : ''}`}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
