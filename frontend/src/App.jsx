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
import FuelOutages from './components/FuelOutages/FuelOutages';
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
          <h2>Victorian transport intelligence</h2>
        </div>
      </header>

      <TabNav tabs={TABS} active={tab} onChange={setTab} />

      <main className="app-main">
        {tab === 'monitor' && (
          <>
            <section className="panel-hero">
              <h3 className="panel-title">Weekly traffic — metro core stations (top 25% by volume)</h3>
              <p className="panel-note">SCATS loop detectors · top 25% by volume · weekday average</p>
              <MetricCards data={monitorData} />
              <WeeklyTrendChart />
            </section>
            <section className="panel-secondary">
              <h3 className="panel-title">Daily traffic — metro core stations</h3>
              <p className="panel-note">Daily vehicle count across top-25% stations · weekdays solid, weekends faded</p>
              <DailyCountsChart />
            </section>
            <section className="panel-secondary">
              <SpeedPanel />
            </section>
            <section className="panel-secondary">
              <h3 className="panel-title">Month-on-month — metro core stations</h3>
              <MonthTable />
            </section>
          </>
        )}

        {tab === 'patterns' && (
          <>
            <section className="panel-hero">
              <h3 className="panel-title">Traffic intensity — hour × day of week</h3>
              <p className="panel-note">~3,860 SCATS stations · last 12 weeks · avg vehicles per 15-min interval</p>
              <HeatmapChart />
            </section>
            <div className="panel-grid panel-grid--stretch">
              <section className="panel-secondary panel-fill">
                <h3 className="panel-title">Hourly profile — year comparison</h3>
                <p className="panel-note">Avg vehicles per 15-min interval per hour · toggle weekday/Sat/Sun · TIRTL speed overlay</p>
                <HourlyProfileChart />
              </section>
              <section className="panel-secondary panel-fill">
                <h3 className="panel-title">Day of week — business hours</h3>
                <p className="panel-note">Avg vehicles/hr/station · 7am–6pm · full 2025 calendar year</p>
                <DayOfWeekChart />
              </section>
            </div>
            <section className="panel-secondary">
              <h3 className="panel-title">Weekday drift — 2024 / 2025 / 2026</h3>
              <p className="panel-note">Business-hours weekday traffic shift year-on-year · excludes public holidays</p>
              <WeekdayDrift />
            </section>
          </>
        )}

        {tab === 'fuel' && (
          <>
            <section className="panel-hero">
              <h3 className="panel-title">VIC fuel prices — state average</h3>
              <FuelStateAvg />
            </section>
            <section className="panel-secondary">
              <h3 className="panel-title">Fuel supply outages</h3>
              <p className="panel-note">Stations reporting fuel unavailable · excludes stations that don't stock a given type · Servo Saver mandatory reporting</p>
              <FuelOutages />
            </section>
            <section className="panel-secondary">
              <h3 className="panel-title">Oil to pump — price transmission chain</h3>
              <FuelPriceChain />
            </section>
            <section className="panel-secondary">
              <h3 className="panel-title">Traffic volume vs fuel price</h3>
              <FuelTrafficOverlay />
            </section>
            <section className="panel-secondary">
              <h3 className="panel-title">Vehicle fleet — fuel type</h3>
              <p className="panel-note">Victorian registered vehicles by fuel type · ABS Motor Vehicle Census</p>
              <FleetBreakdown />
            </section>
            <section className="panel-secondary">
              <h3 className="panel-title">Find cheapest fuel by postcode</h3>
              <FuelByPostcode />
            </section>
          </>
        )}

        {tab === 'transport' && (
          <>
            <section className="panel-hero">
              <h3 className="panel-title">Public transport patronage — Victoria</h3>
              <PTPatronageChart />
            </section>
            <section className="panel-secondary">
              <h3 className="panel-title">Vehicle mix — cars vs trucks (TIRTL sensors, March 2026)</h3>
              <p className="panel-note">288 TIRTL sites · infra-red wheelbase classification · Austroads vehicle categories</p>
              <VehicleMixChart />
            </section>
            <section className="panel-secondary">
              <h3 className="panel-title">Daily patronage by day type (2025 avg)</h3>
              <PTDayTypeChart />
            </section>
          </>
        )}

        {tab === 'aviation' && (
          <AviationPanel />
        )}

        {tab === 'explorer' && (
          <section className="panel-hero">
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
            <section className="panel-hero">
              <h3 className="panel-title">School holiday effect — metro core stations</h3>
              <SchoolHolidayChart />
            </section>
            <section className="panel-secondary">
              <h3 className="panel-title">Peak and quiet days — metro core stations</h3>
              <p className="panel-note">Busiest and quietest weekdays since Jan 2024 · top-25% stations · holidays and events flagged</p>
              <PeakDaysTable />
            </section>
            <section className="panel-secondary">
              <h3 className="panel-title">Event impact on traffic — metro core stations</h3>
              <p className="panel-note">Event window (±1 day) vs day-of-week matched 4-week baseline · negative = less traffic than normal</p>
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
