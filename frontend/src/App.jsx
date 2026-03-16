/**
 * App — main layout for the AMIP dashboard.
 * Manages city selection, tab navigation, and renders chart panels.
 */
import { useState } from 'react';
import CitySelector from './components/CitySelector/CitySelector';
import TabNav from './components/TabNav/TabNav';
import MetricCards from './components/MetricCards/MetricCards';
import WeeklyTrendChart from './components/WeeklyTrendChart/WeeklyTrendChart';
import DailyCountsChart from './components/DailyCountsChart/DailyCountsChart';
import HourlyProfileChart from './components/HourlyProfileChart/HourlyProfileChart';
import DayOfWeekChart from './components/DayOfWeekChart/DayOfWeekChart';
import HeatmapChart from './components/HeatmapChart/HeatmapChart';
import StationMap from './components/StationMap/StationMap';
import StationProfile from './components/StationProfile/StationProfile';
import MonthTable from './components/MonthTable/MonthTable';
import SchoolHolidayChart from './components/SchoolHolidayChart/SchoolHolidayChart';
import SpeedPanel from './components/SpeedPanel/SpeedPanel';
import PTPatronageChart from './components/PTPatronageChart/PTPatronageChart';
import FleetBreakdown from './components/FleetBreakdown/FleetBreakdown';
import { useTrafficData } from './hooks/useTrafficData';
import './styles/global.css';
import './App.css';

const TABS = [
  { id: 'monitor', label: 'Monitor' },
  { id: 'patterns', label: 'Patterns' },
  { id: 'transport', label: 'Transport' },
  { id: 'explorer', label: 'Explorer' },
  { id: 'analysis', label: 'Analysis' },
];

export default function App() {
  const [city, setCity] = useState('melbourne');
  const [tab, setTab] = useState('monitor');
  const [selectedStation, setSelectedStation] = useState(null);
  const { data: monitorData } = useTrafficData('/api/monitor/');

  const cityMonitor = monitorData?.[city];

  const handleCityChange = (newCity) => {
    setCity(newCity);
    setSelectedStation(null);
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-brand">
          <h1>Traffic Movement</h1>
          <h2>Sydney · Melbourne — live traffic intelligence</h2>
        </div>
        <CitySelector city={city} onChange={handleCityChange} />
      </header>

      <TabNav tabs={TABS} active={tab} onChange={setTab} />

      <main className="app-main">
        {tab === 'monitor' && (
          <>
            <section className="panel">
              <h3 className="panel-title">Fuel crisis tracker</h3>
              <MetricCards data={cityMonitor} />
              <WeeklyTrendChart city={city} />
            </section>
            <section className="panel">
              <h3 className="panel-title">Daily traffic</h3>
              <DailyCountsChart city={city} />
            </section>
            <SpeedPanel city={city} />
          </>
        )}

        {tab === 'patterns' && (
          <>
            <section className="panel">
              <h3 className="panel-title">Hour × day of week</h3>
              <HeatmapChart city={city} />
            </section>
            <div className="panel-grid">
              <section className="panel">
                <h3 className="panel-title">Weekday hourly profile</h3>
                <HourlyProfileChart city={city} />
              </section>
              <section className="panel">
                <h3 className="panel-title">Day of week</h3>
                <DayOfWeekChart city={city} />
              </section>
            </div>
          </>
        )}

        {tab === 'transport' && (
          <>
            <section className="panel">
              <h3 className="panel-title">Public transport patronage — Victoria</h3>
              <PTPatronageChart />
            </section>
            <section className="panel">
              <h3 className="panel-title">Vehicle fleet — fuel type breakdown</h3>
              <FleetBreakdown />
            </section>
          </>
        )}

        {tab === 'explorer' && (
          <section className="panel">
            <div className="station-explorer">
              <StationMap
                city={city}
                onSelectStation={setSelectedStation}
                selectedStation={selectedStation}
              />
              {selectedStation && (
                <StationProfile
                  stationId={selectedStation}
                  onClose={() => setSelectedStation(null)}
                />
              )}
            </div>
          </section>
        )}

        {tab === 'analysis' && (
          <>
            <section className="panel">
              <h3 className="panel-title">Month-on-month comparison</h3>
              <MonthTable city={city} />
            </section>
            <section className="panel">
              <h3 className="panel-title">School holiday effect</h3>
              <SchoolHolidayChart city={city} />
            </section>
          </>
        )}
      </main>

      <footer className="app-footer">
        <p>
          Data: TfNSW (Sydney, 26 reliable stations) · VIC DTP SCATS (Melbourne, ~3,860 sites)
          {monitorData?.data_freshness &&
            <> · Latest: NSW {monitorData.data_freshness.NSW}, VIC {monitorData.data_freshness.VIC}</>
          }
        </p>
      </footer>
    </div>
  );
}
