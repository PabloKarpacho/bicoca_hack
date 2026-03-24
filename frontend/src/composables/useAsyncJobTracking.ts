import { storeToRefs } from 'pinia';
import { useAsyncJobsStore } from '../stores/async-jobs';

export function useAsyncJobTracking() {
  const store = useAsyncJobsStore();
  const { snapshots, trackerList } = storeToRefs(store);

  return {
    snapshots,
    trackerList,
    getSnapshot: store.getSnapshot,
    startTracking: store.startTracking,
    stopTracking: store.stopTracking,
    clearCompleted: store.clearCompleted,
  };
}
