import type { ApiClients } from './contracts';
import { createPlaceholderApiClients } from './placeholder';

let apiClients: ApiClients = createPlaceholderApiClients();
let configured = false;

export function configureApiClients(nextClients: ApiClients): void {
  apiClients = nextClients;
  configured = true;
}

export function getApiClients(): ApiClients {
  return apiClients;
}

export function isApiConfigured(): boolean {
  return configured;
}
