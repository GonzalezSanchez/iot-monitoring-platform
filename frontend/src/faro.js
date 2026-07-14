import { getWebInstrumentations, initializeFaro } from '@grafana/faro-web-sdk';
import { TracingInstrumentation } from '@grafana/faro-web-tracing';

// VITE_FARO_URL is only set in production builds (GitHub secret → Docker build
// arg), so local dev builds send no telemetry.
const faroUrl = import.meta.env.VITE_FARO_URL;

if (faroUrl) {
  initializeFaro({
    url: faroUrl,
    app: {
      name: 'iot-frontend',
      version: '1.0.0',
      environment: 'production',
    },
    instrumentations: [
      ...getWebInstrumentations(),
      new TracingInstrumentation(),
    ],
  });
}
