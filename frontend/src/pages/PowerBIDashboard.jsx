import PageHeader from '../components/PageHeader';

const POWERBI_URL =
  'https://app.powerbi.com/view?r=eyJrIjoiMmIwODEyOTEtZDkyMy00ZDRhLTk5M2YtYmM2ZmEzZDI0NWQ5IiwidCI6IjA5YWYzNGNmLTZkY2QtNGFhNS04ZTY1LTVlNDdhODczNGJjOCIsImMiOjl9';

const POWERBI_ENABLED = import.meta.env.VITE_POWERBI_ENABLED === 'true';

const SCREENSHOTS = [
  {
    src: '/screenshots/project2b/project2b-powerbi-temperature-trend.png',
    caption: 'Temperature Trend per room — linear regression slope via PySpark regr_slope',
  },
  {
    src: '/screenshots/project2b/project2b-powerbi-patterns-summary.png',
    caption: 'Patterns Summary — occupancy schedule and temperature trend per room',
  },
  {
    src: '/screenshots/project2b/project2b-powerbi-anomaly-overview.png',
    caption: 'Anomaly Overview — z-score severity per room',
  },
];

// ── Static export (Power BI free tier does not support external embedding) ────

function StaticExport() {
  return (
    <div className="px-6 py-6 max-w-3xl mx-auto">
      <div className="mb-6 p-4 rounded-xl border border-blue-200 bg-blue-50 text-sm text-blue-900">
        The pipeline and its PostgreSQL marts run live (see the project README for the full
        architecture). This report is shown as a static export because Power BI's free tier
        does not support external embedding beyond the trial period.
      </div>
      <div className="space-y-8">
        {SCREENSHOTS.map(({ src, caption }) => (
          <figure key={src} className="m-0">
            <img src={src} alt={caption} className="w-full rounded-xl border border-gray-200" />
            <figcaption className="mt-2 text-sm text-gray-500">{caption}</figcaption>
          </figure>
        ))}
      </div>
    </div>
  );
}

function PowerBIDashboard() {
  return (
    <div className="flex flex-col h-full font-sans overflow-y-auto">
      <PageHeader
        title="Behavior Pattern Analyzer"
        subtitle="Airflow + PySpark + Power BI — DynamoDB → S3 data lake → PostgreSQL"
      />
      {POWERBI_ENABLED ? (
        <div className="flex-1">
          <iframe
            title="Behavior Analyzer — Power BI"
            src={POWERBI_URL}
            allowFullScreen
            className="w-full h-full border-0"
          />
        </div>
      ) : (
        <StaticExport />
      )}
    </div>
  );
}

export default PowerBIDashboard;
