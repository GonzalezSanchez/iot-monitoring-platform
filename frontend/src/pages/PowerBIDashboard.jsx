import PageHeader from '../components/PageHeader';

const POWERBI_URL =
  'https://app.powerbi.com/view?r=eyJrIjoiMmIwODEyOTEtZDkyMy00ZDRhLTk5M2YtYmM2ZmEzZDI0NWQ5IiwidCI6IjA5YWYzNGNmLTZkY2QtNGFhNS04ZTY1LTVlNDdhODczNGJjOCIsImMiOjl9';

function PowerBIDashboard() {
  return (
    <div className="flex flex-col h-full font-sans">
      <PageHeader
        title="Behavior Pattern Analyzer"
        subtitle="Airflow + PySpark + Power BI — DynamoDB → S3 data lake → PostgreSQL"
      />
      <div className="flex-1">
        <iframe
          title="Behavior Analyzer — Power BI"
          src={POWERBI_URL}
          allowFullScreen
          className="w-full h-full border-0"
        />
      </div>
    </div>
  );
}

export default PowerBIDashboard;
