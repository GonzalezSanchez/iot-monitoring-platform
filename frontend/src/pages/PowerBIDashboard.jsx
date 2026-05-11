const POWERBI_URL =
  'https://app.powerbi.com/view?r=eyJrIjoiODFiMjdhOTItYTM2MC00MTQ1LThiYWYtMDk1MzcwMzI4N2Q5IiwidCI6IjA5YWYzNGNmLTZkY2QtNGFhNS04ZTY1LTVlNDdhODczNGJjOCIsImMiOjl9';

function PowerBIDashboard() {
  return (
    <div className="flex flex-col h-full font-sans">
      <div className="px-6 py-4 border-b border-gray-200 bg-white shrink-0">
        <h1 className="text-2xl font-bold text-gray-900">Behavior Pattern Analyzer</h1>
        <p className="mt-1 text-sm text-gray-500">
          Airflow + PySpark + Power BI — DynamoDB → S3 data lake → PostgreSQL
        </p>
      </div>
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
