export class ApiIntegrationNotConfiguredError extends Error {
  constructor() {
    super(
      'API integration is not configured yet. Replace the placeholder clients in src/api to connect the frontend to the backend service.',
    );
    this.name = 'ApiIntegrationNotConfiguredError';
  }
}
