/**
 * App — main layout for the AMIP dashboard.
 * Manages city selection state and renders chart panels.
 */
import { useState } from 'react';
import CitySelector from './components/CitySelector/CitySelector';
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
import { useTrafficData } from './hooks/useTrafficData';
import './styles/global.css';
import './App.css';

export default function App() {
  const [city, setCity] = useState('melbourne');
  const [selectedStation, setSelectedStation] = useState(null);
  const { data: monitorData } = useTrafficData('/api/monitor/');

  const cityMonitor = monitorData?.[city];

  // Clear station selection when city changes
  const handleCityChange = (newCity) => {
    setCity(newCity);
    setSelectedStation(null);
  };

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>Traffic Movement</h1>
          <h2>Australia Mobility Intelligence Platform</h2>
        </div>
        <CitySelector city={city} onChange={handleCityChange} />
      </header>

      <main className="app-main">
        <section className="panel">
          <h3 className="panel-title">Weekly monitor — fuel crisis tracker</h3>
          <MetricCards data={cityMonitor} />
          <WeeklyTrendChart city={city} />
        </section>

        <section className="panel">
          <h3 className="panel-title">Daily traffic — are people driving less?</h3>
          <DailyCountsChart city={city} />
        </section>

        <section className="panel">
          <h3 className="panel-title">Traffic heatmap — hour × day of week (last 12 weeks)</h3>
          <HeatmapChart city={city} />
        </section>

        <section className="panel">
          <h3 className="panel-title">Station explorer — click a station to see its profile</h3>
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

        <section className="panel">
          <h3 className="panel-title">Month-on-month comparison (weekday average per station)</h3>
          <MonthTable city={city} />
        </section>

        <div className="panel-grid">
          <section className="panel">
            <h3 className="panel-title">Weekday hourly profile</h3>
            <HourlyProfileChart city={city} />
          </section>
          <section className="panel">
            <h3 className="panel-title">Day of week (2025)</h3>
            <DayOfWeekChart city={city} />
          </section>
        </div>

        <section className="panel">
          <h3 className="panel-title">School holiday effect on traffic</h3>
          <SchoolHolidayChart city={city} />
        </section>

        <footer className="app-footer">
          <p>
            Data: TfNSW (Sydney, 26 reliable stations) · VIC DTP SCATS (Melbourne, ~3,860 sites)
            {monitorData?.data_freshness &&
              ` · Latest: NSW ${monitorData.data_freshness.NSW}, VIC ${monitorData.data_freshness.VIC}`
            }
          </p>
        </footer>
      </main>
    </div>
  );
}
