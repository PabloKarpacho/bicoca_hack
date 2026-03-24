export type AsyncOperationState =
  | 'idle'
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed';

export interface AsyncTrackingTarget {
  kind: 'document' | 'job';
  id: string;
}

export interface AsyncJobSnapshot {
  id: string;
  resourceKind: AsyncTrackingTarget['kind'];
  state: AsyncOperationState;
  stageLabel?: string | null;
  message?: string | null;
  errorMessage?: string | null;
  isTerminal: boolean;
  updatedAt?: string | null;
}

export function createPendingSnapshot(target: AsyncTrackingTarget): AsyncJobSnapshot {
  return {
    id: target.id,
    resourceKind: target.kind,
    state: 'pending',
    stageLabel: 'Queued',
    message: 'Waiting for backend processing',
    isTerminal: false,
    updatedAt: new Date().toISOString(),
  };
}
