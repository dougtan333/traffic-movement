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
import PeakDaysTable from './components/PeakDaysTable/PeakDaysTable';
import EventImpact from './components/EventImpact/EventImpact';
import WeekdayDrift from './components/WeekdayDrift/WeekdayDrift';
import SpeedPanel from './components/SpeedPanel/SpeedPanel';
import PTPatronageChart from './components/PTPatronageChart/PTPatronageChart';
import PTDayTypeChart from './components/PTDayTypeChart/PTDayTypeChart';
import FleetBreakdown from './components/FleetBreakdown/FleetBreakdown';
import VehicleMixChart from './components/VehicleMixChart/VehicleMixChart';
import FuelPriceChain from './components/FuelPriceChain/FuelPriceChain';
import FuelTrafficOverlay from './components/FuelTrafficOverlay/FuelTrafficOverlay';
import FuelByPostcode from './components/FuelByPostcode/FuelByPostcode';
import FuelStateAvg from './components/FuelStateAvg/FuelStateAvg';
import AviationPanel from './components/AviationPanel/AviationPanel';
import { useTrafficData } from './hooks/useTrafficData';
import './styles/global.css';
import './App.css';

const TABS = [
  { id: 'monitor', label: 'Monitor' },
  { id: 'patterns', label: 'Patterns' },
  { id: 'fuel', label: 'Fuel' },
  { id: 'transport', label: 'Transport' },
  { id: 'explorer', label: 'Explorer' },
  { id: 'analysis', label: 'Occasions' },
  { id: 'aviation', label: 'Aviation' },
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
                <p className="panel-note">Average vehicles per 15-min interval per station at each hour. Toggle between weekdays, Saturday, and Sunday. Overlays multiple years. Red dashed line = average freeway speed from TIRTL sensors (right axis).</p>
                <HourlyProfileChart />
              </section>
              <section className="panel">
                <h3 className="panel-title">Day of week — business hours</h3>
                <p className="panel-note">Average vehicles per hour per station, 7am–6pm only, across all ~3,860 SCATS stations. Averaged over the full 2025 calendar year (Jan–Dec). Weekend bars faded.</p>
                <DayOfWeekChart />
              </section>
            </div>
            <section className="panel">
              <h3 className="panel-title">Weekday drift — 2024 vs 2025</h3>
              <p className="panel-note">Has the shape of the work week changed? Compares average weekday traffic (business hours, excluding public holidays) between 2024 and 2025 to detect shifts like quieter Fridays or busier mid-week days.</p>
              <WeekdayDrift />
            </section>
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
              <h3 className="panel-title">Vehicle fleet — fuel type</h3>
              <p className="panel-note">Victorian registered vehicle fleet by fuel type. Source: ABS Motor Vehicle Census.</p>
              <FleetBreakdown />
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
              <p className="panel-note">TIRTL (Traffic Infra-Red Logger) sensors classify vehicles by measuring wheelbase distance — the gap between axle groups as a vehicle passes over twin infra-red beams. Short wheelbase = car. Wider axle spacing or more axle groups = rigid truck, articulated truck, B-double, or bus. 288 TIRTL sites across Victorian freeways.</p>
              <VehicleMixChart />
            </section>
            <section className="panel">
              <h3 className="panel-title">Daily patronage by day type (2025 avg)</h3>
              <PTDayTypeChart />
            </section>
          </>
        )}

        {tab === 'aviation' && (
          <AviationPanel />
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
              <h3 className="panel-title">School holiday effect — metro core stations</h3>
              <SchoolHolidayChart />
            </section>
            <section className="panel">
              <h3 className="panel-title">Month-on-month — metro core stations</h3>
              <MonthTable />
            </section>
            <section className="panel">
              <h3 className="panel-title">Peak and quiet days — metro core stations</h3>
              <p className="panel-note">Ranking the busiest and quietest weekdays since Jan 2024 across the top-25% stations by volume. Context column shows public holidays, school holidays, or named events where applicable.</p>
              <PeakDaysTable />
            </section>
            <section className="panel">
              <h3 className="panel-title">Event impact on traffic — metro core stations</h3>
              <p className="panel-note">Compares average traffic during the event window (event day ± 1 day) against a day-of-week matched baseline from the surrounding 4 weeks. Negative = less traffic than normal (event draws people off the road or onto PT).</p>
              <EventImpact />
            </section>
          </>
        )}
      </main>

      <footer className="app-footer">
        <p>
          Data: VIC DTP — SCATS (~3,860 sites) · Bluetooth speed (4,711 links) · TIRTL (288 sites) · PT patronage · Vehicle registrations
          {' · '}Service VIC Servo Saver (1,678 fuel stations) · AIP wholesale prices · EIA Brent crude
          {' · '}BITRE airport traffic (5 airports)
          {monitorData?.data_freshness &&
            <> · Latest: {monitorData.data_freshness}</>
          }
        </p>
      </footer>
    </div>
  );
}
