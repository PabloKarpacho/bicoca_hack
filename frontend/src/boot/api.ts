import { boot } from 'quasar/wrappers';
import { configureApiClients } from '../api';
import { createBackendApiClients } from '../api/backend';

export default boot(() => {
  configureApiClients(createBackendApiClients());
});
