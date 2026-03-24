<template>
  <q-card flat bordered class="app-panel candidate-card">
    <q-card-section class="row items-start justify-between q-col-gutter-md">
      <div class="col">
        <div class="text-h6">{{ result.displayName }}</div>
        <div class="text-subtitle2 text-grey-8">{{ roleLabel }}</div>
        <div class="text-body2 text-grey-7 q-mt-xs">{{ locationLabel }}</div>
      </div>

      <div class="column items-end q-gutter-sm">
        <status-chip status="completed" :label="scoreLabel" />
        <div class="text-caption text-grey-7">Experience: {{ experienceLabel }}</div>
      </div>
    </q-card-section>

    <q-separator />

    <q-card-section class="column q-gutter-md">
      <div v-if="result.headline" class="text-body1">{{ result.headline }}</div>
      <div v-if="result.summary" class="text-body2 text-grey-8">
        {{ result.summary }}
      </div>

      <div class="row q-col-gutter-lg">
        <div
          v-for="section in matchSections"
          :key="section.title"
          class="col-12 col-md-6"
        >
          <div class="text-caption text-grey-7 q-mb-xs">{{ section.title }}</div>
          <div class="row q-gutter-xs">
            <q-chip
              v-for="value in section.values"
              :key="`${section.title}-${value}`"
              dense
              square
              :color="section.color"
              text-color="white"
            >
              {{ value }}
            </q-chip>
            <span v-if="section.values.length === 0" class="text-body2 text-grey-6">
              {{ section.emptyLabel }}
            </span>
          </div>
        </div>
      </div>

      <div v-if="educationChip" class="column q-gutter-xs">
        <div class="text-caption text-grey-7">Education compatibility</div>
        <div class="row items-center q-gutter-sm">
          <q-chip
            :color="educationChip?.color"
            text-color="white"
            :icon="educationChip?.icon"
          >
            {{ educationChip?.label }}
          </q-chip>
          <span v-if="educationNote" class="text-body2 text-grey-7">
            {{ educationNote }}
          </span>
        </div>
      </div>
    </q-card-section>

    <q-card-actions align="between">
      <div class="text-caption text-grey-6">Candidate ID: {{ result.candidateId }}</div>
      <q-btn
        color="primary"
        icon="open_in_new"
        label="Open resume"
        target="_blank"
        rel="noopener"
        :disable="!result.resumeUrl"
        :href="result.resumeUrl ?? undefined"
      />
    </q-card-actions>
  </q-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { CandidateSearchResultItem } from '../../types/search';
import { formatMonths } from '../../utils/formatting';
import StatusChip from '../shared/StatusChip.vue';

const props = defineProps<{
  result: CandidateSearchResultItem;
}>();

type MatchSection = {
  title: string;
  values: string[];
  color: string;
  emptyLabel: string;
};

type EducationChip = {
  color: string;
  icon: string;
  label: string;
};

const roleLabel = computed(() => {
  const role = props.result.currentRole || 'Role not specified';
  return props.result.seniority ? `${role} · ${props.result.seniority}` : role;
});

const locationLabel = computed(() => props.result.location || 'Location not specified');

const experienceLabel = computed(() => formatMonths(props.result.totalExperienceMonths));

const scoreLabel = computed(() => {
  if (props.result.matchScorePercent != null) {
    return `Match ${props.result.matchScorePercent}%`;
  }

  if (props.result.score == null) {
    return 'Shortlist';
  }

  return `Score ${props.result.score.toFixed(2)}`;
});

const matchSections = computed<MatchSection[]>(() => [
  {
    title: 'Matched skills',
    values: props.result.matchedSkills ?? [],
    color: 'primary',
    emptyLabel: 'No explicit matches',
  },
  {
    title: 'Matched languages',
    values: props.result.matchedLanguages ?? [],
    color: 'secondary',
    emptyLabel: 'No explicit matches',
  },
  {
    title: 'Employment compatibility',
    values: props.result.matchMetadata?.matchedEmploymentTypes ?? [],
    color: 'teal',
    emptyLabel: 'No explicit overlap',
  },
]);

const educationNote = computed(() => props.result.matchMetadata?.educationMatchNote ?? null);

const educationChip = computed<EducationChip | null>(() => {
  const status = props.result.matchMetadata?.educationMatchStatus;
  if (status === 'matched') {
    return { color: 'positive', icon: 'school', label: 'Education matched' };
  }
  if (status === 'partial') {
    return { color: 'warning', icon: 'rule', label: 'Education partially matched' };
  }
  if (status === 'mismatch') {
    return { color: 'negative', icon: 'report_problem', label: 'Education mismatch' };
  }
  return null;
});
</script>
