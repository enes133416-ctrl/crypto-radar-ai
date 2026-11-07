export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  run_mode: string;
  demo_mode: boolean;
  server_time: string;
}
