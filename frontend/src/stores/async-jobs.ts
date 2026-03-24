import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { getApiClients } from '../api';
import type { AsyncJobSnapshot, AsyncTrackingTarget } from '../types/jobs';
import { createPendingSnapshot } from '../types/jobs';

interface StartTrackingOptions {
  intervalMs?: number;
  onUpdate?: (snapshot: AsyncJobSnapshot) => void;
}

function trackerKey(target: AsyncTrackingTarget): string {
  return `${target.kind}:${target.id}`;
}

export const useAsyncJobsStore = defineStore('async-jobs', () => {
  const snapshots = ref<Record<string, AsyncJobSnapshot>>({});
  const timers = new Map<string, ReturnType<typeof setTimeout>>();

  const trackerList = computed(() => Object.values(snapshots.value));

  function setSnapshot(snapshot: AsyncJobSnapshot): void {
    snapshots.value = {
      ...snapshots.value,
      [trackerKey({ kind: snapshot.resourceKind, id: snapshot.id })]: snapshot,
    };
  }

  function getSnapshot(target: AsyncTrackingTarget): AsyncJobSnapshot | undefined {
    return snapshots.value[trackerKey(target)];
  }

  function stopTracking(target: AsyncTrackingTarget): void {
    const key = trackerKey(target);
    const timer = timers.get(key);
    if (timer) {
      clearTimeout(timer);
      timers.delete(key);
    }
  }

  async function refresh(target: AsyncTrackingTarget): Promise<AsyncJobSnapshot> {
    const snapshot = await getApiClients().jobs.getAsyncStatus(target);
    setSnapshot(snapshot);
    return snapshot;
  }

  function startTracking(target: AsyncTrackingTarget, options: StartTrackingOptions = {}): void {
    const intervalMs = options.intervalMs ?? 4000;
    stopTracking(target);
    setSnapshot(createPendingSnapshot(target));

    const run = async () => {
      try {
        const snapshot = await refresh(target);
        options.onUpdate?.(snapshot);

        if (snapshot.isTerminal) {
          stopTracking(target);
          return;
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Status polling failed';
        const failedSnapshot: AsyncJobSnapshot = {
          id: target.id,
          resourceKind: target.kind,
          state: 'failed',
          stageLabel: 'Status check failed',
          message: 'Could not refresh async operation state',
          errorMessage: message,
          isTerminal: true,
          updatedAt: new Date().toISOString(),
        };
        setSnapshot(failedSnapshot);
        options.onUpdate?.(failedSnapshot);
        stopTracking(target);
        return;
      }

      timers.set(
        trackerKey(target),
        setTimeout(() => {
          void run();
        }, intervalMs),
      );
    };

    void run();
  }

  function clearCompleted(): void {
    const nextSnapshots: Record<string, AsyncJobSnapshot> = {};

    for (const snapshot of Object.values(snapshots.value)) {
      if (!snapshot.isTerminal) {
        nextSnapshots[trackerKey({ kind: snapshot.resourceKind, id: snapshot.id })] = snapshot;
      }
    }

    snapshots.value = nextSnapshots;
  }

  return {
    snapshots,
    trackerList,
    getSnapshot,
    startTracking,
    stopTracking,
    clearCompleted,
  };
});
