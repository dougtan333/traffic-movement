/**
 * App — main layout for the AMIP dashboard.
 * Victoria-only. Tab navigation and chart panels.
 */
import { useState } from 'react';
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
import PTDayTypeChart from './components/PTDayTypeChart/PTDayTypeChart';
import FleetBreakdown from './components/FleetBreakdown/FleetBreakdown';
import VehicleMixChart from './components/VehicleMixChart/VehicleMixChart';
import TIRTLSpeedChart from './components/TIRTLSpeedChart/TIRTLSpeedChart';
import FuelPriceChain from './components/FuelPriceChain/FuelPriceChain';
import FuelTrafficOverlay from './components/FuelTrafficOverlay/FuelTrafficOverlay';
import FuelByPostcode from './components/FuelByPostcode/FuelByPostcode';
import FuelStateAvg from './components/FuelStateAvg/FuelStateAvg';
import { useTrafficData } from './hooks/useTrafficData';
import './styles/global.css';
import './App.css';

const TABS = [
  { id: 'monitor', label: 'Monitor' },
  { id: 'patterns', label: 'Patterns' },
  { id: 'fuel', label: 'Fuel' },
  { id: 'transport', label: 'Transport' },
  { id: 'explorer', label: 'Explorer' },
  { id: 'analysis', label: 'Analysis' },
];

export default function App() {
  const [tab, setTab] = useState('monitor');
  const [selectedStation, setSelectedStation] = useState(null);
  const { data: monitorData } = useTrafficData('/api/monitor/');

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-brand">
          <h1>Traffic Movement</h1>
          <h2>Victorian transport intelligence — traffic, speed, fuel prices, PT, fleet</h2>
        </div>
      </header>

      <TabNav tabs={TABS} active={tab} onChange={setTab} />

      <main className="app-main">
        {tab === 'monitor' && (
          <>
            <section className="panel">
              <h3 className="panel-title">Weekly traffic — metro core stations (top 25% by volume)</h3>
              <p className="panel-note">A station is a SCATS loop detector at a signalised intersection, counting vehicles every 15 minutes. Metro core = the busiest quarter of Melbourne's ~3,860 stations.</p>
              <MetricCards data={monitorData} />
              <WeeklyTrendChart />
            </section>
            <section className="panel">
              <h3 className="panel-title">Daily traffic — metro core stations</h3>
              <p className="panel-note">Daily vehicle count averaged across the same top-25% stations. Weekdays shown in solid, weekends and holidays faded.</p>
              <DailyCountsChart />
            </section>
            <SpeedPanel />
          </>
        )}

        {tab === 'patterns' && (
          <>
            <section className="panel">
              <h3 className="panel-title">Traffic intensity — hour × day of week</h3>
              <p className="panel-note">Average vehicles per 15-min interval per station, across all ~3,860 SCATS stations over the last 12 weeks. Darker cells = busier periods.</p>
              <HeatmapChart />
            </section>
            <div className="panel-grid">
              <section className="panel">
                <h3 className="panel-title">Hourly profile — year comparison</h3>
                <p className="panel-note">Average vehicles per 15-min interval per station at each hour. Toggle between weekdays, Saturday, and Sunday. Overlays multiple years.</p>
                <HourlyProfileChart />
              </section>
              <section className="panel">
                <h3 className="panel-title">Day of week — business hours</h3>
                <p className="panel-note">Average vehicles per hour per station, 7am–6pm only, across all stations. Weekend bars faded.</p>
                <DayOfWeekChart />
              </section>
            </div>
          </>
        )}

        {tab === 'fuel' && (
          <>
            <section className="panel">
              <h3 className="panel-title">VIC fuel prices — state average</h3>
              <FuelStateAvg />
            </section>
            <section className="panel">
              <h3 className="panel-title">Oil to pump — price transmission chain</h3>
              <FuelPriceChain />
            </section>
            <section className="panel">
              <h3 className="panel-title">Traffic volume vs fuel price</h3>
              <FuelTrafficOverlay />
            </section>
            <section className="panel">
              <h3 className="panel-title">Find cheapest fuel by postcode</h3>
              <FuelByPostcode />
            </section>
          </>
        )}

        {tab === 'transport' && (
          <>
            <section className="panel">
              <h3 className="panel-title">Public transport patronage — Victoria</h3>
              <PTPatronageChart />
            </section>
            <section className="panel">
              <h3 className="panel-title">Vehicle mix — cars vs trucks (TIRTL sensors, March 2026)</h3>
              <VehicleMixChart />
            </section>
            <div className="panel-grid">
              <section className="panel">
                <h3 className="panel-title">Freeway speed profile — weekday vs weekend</h3>
                <TIRTLSpeedChart />
              </section>
              <section className="panel">
                <h3 className="panel-title">Vehicle fleet — fuel type</h3>
                <FleetBreakdown />
              </section>
            </div>
            <section className="panel">
              <h3 className="panel-title">Daily patronage by day type (2025 avg)</h3>
              <PTDayTypeChart />
            </section>
          </>
        )}

        {tab === 'explorer' && (
          <section className="panel">
            <div className="station-explorer">
              <StationMap
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
              <h3 className="panel-title">Month-on-month — metro core stations</h3>
              <MonthTable />
            </section>
            <section className="panel">
              <h3 className="panel-title">School holiday effect — metro core stations</h3>
              <SchoolHolidayChart />
            </section>
          </>
        )}
      </main>

      <footer className="app-footer">
        <p>
          Data: VIC DTP — SCATS (~3,860 sites) · Bluetooth speed (4,711 links) · TIRTL (288 sites) · PT patronage · Vehicle registrations
          {' · '}Service VIC Servo Saver (1,678 fuel stations) · AIP wholesale prices · EIA Brent crude
          {monitorData?.data_freshness &&
            <> · Latest: {monitorData.data_freshness}</>
          }
        </p>
      </footer>
    </div>
  );
}
