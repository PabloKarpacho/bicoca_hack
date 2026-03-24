<template>
  <q-card flat bordered class="app-panel">
    <q-card-section class="row items-start justify-between q-col-gutter-md">
      <div class="col">
        <div class="text-h6">Rule-based filters</div>
        <div class="text-body2 text-grey-7 q-mt-xs">
          Configure shortlist criteria and the results will refresh automatically.
        </div>
      </div>

      <div class="col-auto row q-gutter-sm items-center">
        <div v-if="loading" class="row items-center text-body2 text-grey-7 q-gutter-xs">
          <q-spinner size="18px" color="primary" />
          <span>Updating shortlist...</span>
        </div>
        <q-btn flat label="Reset" :disable="loading" @click="$emit('reset')" />
      </div>
    </q-card-section>

    <q-separator />

    <q-card-section class="column q-gutter-xl">
      <section class="column q-gutter-md">
        <div class="text-subtitle1">Role and seniority</div>
        <div class="row q-col-gutter-md">
          <div class="col-12 col-md-6">
            <q-select
              ref="professionSelectRef"
              :model-value="modelValue.currentRoles"
              :options="professionOptions"
              :input-value="professionInput"
              label="Current role / profession"
              use-input
              use-chips
              multiple
              hide-dropdown-icon
              filled
              :loading="professionsLoading"
              new-value-mode="add-unique"
              @filter="handleProfessionFilter"
              @input-value="(value) => updateProfessionInput(value)"
              @update:model-value="updateProfessionArrayField"
            />
          </div>

          <div class="col-12 col-md-3">
            <q-select
              :model-value="modelValue.seniority"
              label="Seniority"
              multiple
              use-chips
              filled
              :options="SENIORITY_OPTIONS"
              @update:model-value="(value) => updateArrayField('seniority', value)"
            />
          </div>

          <div class="col-12 col-md-3">
            <q-input
              :model-value="experienceInput"
              type="number"
              min="0"
              label="Minimum experience (months)"
              filled
              @update:model-value="updateExperience"
            />
          </div>
        </div>
      </section>

      <section class="column q-gutter-md">
        <div class="text-subtitle1">Skills and domains</div>
        <div class="row q-col-gutter-md">
          <div class="col-12 col-md-6">
            <q-select
              ref="includeSkillSelectRef"
              :model-value="modelValue.includeSkills"
              :options="includeSkillOptions"
              :input-value="includeSkillInput"
              label="Include skills"
              use-input
              use-chips
              multiple
              hide-dropdown-icon
              filled
              :loading="includeSkillsLoading"
              new-value-mode="add-unique"
              @filter="(value, update) => handleSkillFilter(value, update, 'include')"
              @input-value="(value) => updateSkillInput(value, 'include')"
              @update:model-value="(value) => updateSkillArrayField('includeSkills', value, 'include')"
            />
          </div>

          <div class="col-12 col-md-6">
            <q-select
              ref="optionalSkillSelectRef"
              :model-value="modelValue.optionalSkills"
              :options="optionalSkillOptions"
              :input-value="optionalSkillInput"
              label="Optional skills"
              use-input
              use-chips
              multiple
              hide-dropdown-icon
              filled
              :loading="optionalSkillsLoading"
              new-value-mode="add-unique"
              @filter="(value, update) => handleSkillFilter(value, update, 'optional')"
              @input-value="(value) => updateSkillInput(value, 'optional')"
              @update:model-value="(value) => updateSkillArrayField('optionalSkills', value, 'optional')"
            />
          </div>

          <div class="col-12 col-md-6">
            <q-select
              :model-value="modelValue.domains"
              label="Domain / industry"
              use-input
              use-chips
              multiple
              hide-dropdown-icon
              filled
              new-value-mode="add-unique"
              @update:model-value="(value) => updateArrayField('domains', value)"
            />
          </div>

          <div class="col-12 col-md-6">
            <q-select
              :model-value="modelValue.employmentTypes"
              label="Employment type"
              multiple
              use-chips
              filled
              :options="EMPLOYMENT_TYPE_OPTIONS"
              @update:model-value="(value) => updateArrayField('employmentTypes', value)"
            />
          </div>
        </div>
      </section>

      <section class="column q-gutter-md">
        <div class="text-subtitle1">Qualifications</div>
        <div class="row q-col-gutter-md">
          <div class="col-12 col-md-6">
            <q-select
              :model-value="modelValue.educationRequirements"
              label="Education requirements"
              multiple
              use-chips
              filled
              :options="EDUCATION_LEVEL_OPTIONS"
              @update:model-value="(value) => updateArrayField('educationRequirements', value)"
            />
          </div>

          <div class="col-12 col-md-6">
            <q-select
              :model-value="modelValue.certificationRequirements"
              label="Certifications"
              use-input
              use-chips
              multiple
              hide-dropdown-icon
              filled
              new-value-mode="add-unique"
              @update:model-value="(value) => updateArrayField('certificationRequirements', value)"
            />
          </div>
        </div>
      </section>

      <section class="column q-gutter-md">
        <div class="text-subtitle1">Languages and location</div>
        <div class="row q-col-gutter-md">
          <div class="col-12 col-md-6">
            <div class="row items-center justify-between q-mb-sm">
              <div class="text-body2 text-grey-7">Language requirements</div>
              <q-btn flat dense icon="add" label="Add language" @click="addLanguage" />
            </div>

            <div v-if="modelValue.languages.length === 0" class="text-body2 text-grey-6">
              No language filters configured.
            </div>

            <div v-for="(language, index) in modelValue.languages" :key="index" class="row q-col-gutter-sm q-mb-sm">
              <div class="col-7">
                <q-input
                  :model-value="language.language"
                  filled
                  label="Language"
                  @update:model-value="
                    (value) => updateLanguage(index, { language: String(value ?? '') })
                  "
                />
              </div>
              <div class="col-4">
                <q-select
                  :model-value="language.minProficiency ?? null"
                  filled
                  clearable
                  label="Min level"
                  :options="PROFICIENCY_OPTIONS"
                  @update:model-value="
                    (value) =>
                      updateLanguage(index, {
                        minProficiency: value ? String(value) : null,
                      })
                  "
                />
              </div>
              <div class="col-1 flex flex-center">
                <q-btn flat round color="negative" icon="delete" @click="removeLanguage(index)" />
              </div>
            </div>
          </div>

          <div class="col-12 col-md-3">
            <q-select
              :model-value="modelValue.locations"
              label="Cities / countries"
              use-input
              use-chips
              multiple
              hide-dropdown-icon
              filled
              new-value-mode="add-unique"
              @update:model-value="(value) => updateArrayField('locations', value)"
            />
          </div>

          <div class="col-12 col-md-3">
            <q-select
              :model-value="modelValue.remotePolicies"
              label="Remote policy"
              multiple
              use-chips
              filled
              :options="REMOTE_POLICY_OPTIONS"
              @update:model-value="(value) => updateArrayField('remotePolicies', value)"
            />
          </div>
        </div>
      </section>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue';
import { getApiClients } from '../../api';
import type {
  CandidateSearchFilters,
  LanguageRequirementFilter,
  SkillSuggestion,
} from '../../types/search';
import {
  EDUCATION_LEVEL_OPTIONS,
  EMPLOYMENT_TYPE_OPTIONS,
  PROFICIENCY_OPTIONS,
  REMOTE_POLICY_OPTIONS,
  SENIORITY_OPTIONS,
} from '../../types/search';

const props = withDefaults(
  defineProps<{
    modelValue: CandidateSearchFilters;
    loading?: boolean;
    disabled?: boolean;
  }>(),
  {
    loading: false,
    disabled: false,
  },
);

const emit = defineEmits<{
  'update:modelValue': [value: CandidateSearchFilters];
  reset: [];
}>();

const experienceInput = computed(() =>
  props.modelValue.minExperienceMonths == null ? '' : String(props.modelValue.minExperienceMonths),
);

const includeSkillOptions = ref<string[]>([]);
const optionalSkillOptions = ref<string[]>([]);
const professionOptions = ref<string[]>([]);
const professionInput = ref('');
const includeSkillInput = ref('');
const optionalSkillInput = ref('');
const professionSelectRef = ref<{
  updateInputValue: (value: string, noFiltering?: boolean, internal?: boolean) => void;
} | null>(null);
const includeSkillSelectRef = ref<{
  updateInputValue: (value: string, noFiltering?: boolean, internal?: boolean) => void;
} | null>(null);
const optionalSkillSelectRef = ref<{
  updateInputValue: (value: string, noFiltering?: boolean, internal?: boolean) => void;
} | null>(null);
const includeSkillsLoading = ref(false);
const optionalSkillsLoading = ref(false);
const professionsLoading = ref(false);
let professionRequestId = 0;
let includeSkillRequestId = 0;
let optionalSkillRequestId = 0;

function logSkillDebug(event: string, payload: Record<string, unknown>): void {
  console.debug(`[CandidateSearchFiltersForm] ${event}`, payload);
}

function emitNext(nextValue: CandidateSearchFilters): void {
  emit('update:modelValue', {
    ...nextValue,
    currentRoles: [...nextValue.currentRoles],
    seniority: [...nextValue.seniority],
    languages: nextValue.languages.map((item) => ({ ...item })),
    includeSkills: [...nextValue.includeSkills],
    optionalSkills: [...nextValue.optionalSkills],
    locations: [...nextValue.locations],
    domains: [...nextValue.domains],
    remotePolicies: [...nextValue.remotePolicies],
    employmentTypes: [...nextValue.employmentTypes],
    educationRequirements: [...nextValue.educationRequirements],
    certificationRequirements: [...nextValue.certificationRequirements],
  });
}

function updateField<K extends keyof CandidateSearchFilters>(
  field: K,
  value: CandidateSearchFilters[K],
): void {
  emitNext({
    ...props.modelValue,
    [field]: value,
  });
}

function updateArrayField<K extends keyof CandidateSearchFilters>(
  field: K,
  value: unknown,
): void {
  const nextValue = (Array.isArray(value) ? [...value] : []) as unknown as CandidateSearchFilters[K];
  updateField(field, nextValue);
}

function updateProfessionInput(value: string | number | null): void {
  professionInput.value = String(value ?? '');
}

function updateProfessionArrayField(value: unknown): void {
  updateArrayField('currentRoles', value);
  professionInput.value = '';
  professionOptions.value = [];
  professionsLoading.value = false;
  professionSelectRef.value?.updateInputValue('', true, true);
  void nextTick(() => {
    professionSelectRef.value?.updateInputValue('', true, true);
  });
}

function updateSkillInput(value: string | number | null, target: 'include' | 'optional'): void {
  const nextValue = String(value ?? '');
  logSkillDebug('skill-input-change', {
    target,
    nextValue,
    includeSkillInput: includeSkillInput.value,
    optionalSkillInput: optionalSkillInput.value,
  });
  if (target === 'include') {
    includeSkillInput.value = nextValue;
    return;
  }
  optionalSkillInput.value = nextValue;
}

function updateSkillArrayField<K extends 'includeSkills' | 'optionalSkills'>(
  field: K,
  value: unknown,
  target: 'include' | 'optional',
): void {
  logSkillDebug('skill-selection-before-clear', {
    field,
    target,
    selectedValue: value,
    includeSkillInput: includeSkillInput.value,
    optionalSkillInput: optionalSkillInput.value,
  });

  updateArrayField(field, value);

  if (target === 'include') {
    includeSkillInput.value = '';
    includeSkillOptions.value = [];
    includeSkillsLoading.value = false;
    includeSkillSelectRef.value?.updateInputValue('', true, true);
    void nextTick(() => {
      includeSkillSelectRef.value?.updateInputValue('', true, true);
    });
    logSkillDebug('skill-selection-after-clear', {
      field,
      target,
      includeSkillInput: includeSkillInput.value,
      optionalSkillInput: optionalSkillInput.value,
      includeSkillOptions: includeSkillOptions.value,
    });
    return;
  }

  optionalSkillInput.value = '';
  optionalSkillOptions.value = [];
  optionalSkillsLoading.value = false;
  optionalSkillSelectRef.value?.updateInputValue('', true, true);
  void nextTick(() => {
    optionalSkillSelectRef.value?.updateInputValue('', true, true);
  });
  logSkillDebug('skill-selection-after-clear', {
    field,
    target,
    includeSkillInput: includeSkillInput.value,
    optionalSkillInput: optionalSkillInput.value,
    optionalSkillOptions: optionalSkillOptions.value,
  });
}

function updateExperience(value: string | number | null): void {
  if (value === '' || value == null) {
    updateField('minExperienceMonths', null);
    return;
  }

  updateField('minExperienceMonths', Number(value));
}

function addLanguage(): void {
  updateField('languages', [
    ...props.modelValue.languages,
    { language: '', minProficiency: null },
  ]);
}

function updateLanguage(index: number, patch: Partial<LanguageRequirementFilter>): void {
  const nextLanguages = props.modelValue.languages.map((item, currentIndex) =>
    currentIndex === index ? { ...item, ...patch } : item,
  );
  updateField('languages', nextLanguages);
}

function removeLanguage(index: number): void {
  updateField(
    'languages',
    props.modelValue.languages.filter((_, currentIndex) => currentIndex !== index),
  );
}

async function loadSkillSuggestions(
  value: string,
  target: 'include' | 'optional',
): Promise<void> {
  const normalizedValue = value.trim();
  logSkillDebug('skill-suggestions-request', {
    target,
    rawValue: value,
    normalizedValue,
  });
  if (normalizedValue.length < 2) {
    if (target === 'include') {
      includeSkillOptions.value = [];
      includeSkillsLoading.value = false;
    } else {
      optionalSkillOptions.value = [];
      optionalSkillsLoading.value = false;
    }
    return;
  }

  const currentRequestId = target === 'include' ? ++includeSkillRequestId : ++optionalSkillRequestId;
  if (target === 'include') {
    includeSkillsLoading.value = true;
  } else {
    optionalSkillsLoading.value = true;
  }

  try {
    const suggestions = await getApiClients().search.suggestSkills(normalizedValue);
    const nextOptions = suggestions.map((item: SkillSuggestion) => item.text);
    logSkillDebug('skill-suggestions-response', {
      target,
      normalizedValue,
      suggestions: nextOptions,
    });
    if (target === 'include') {
      if (currentRequestId !== includeSkillRequestId) return;
      includeSkillOptions.value = nextOptions;
    } else {
      if (currentRequestId !== optionalSkillRequestId) return;
      optionalSkillOptions.value = nextOptions;
    }
  } catch {
    if (target === 'include') {
      if (currentRequestId !== includeSkillRequestId) return;
      includeSkillOptions.value = [];
    } else {
      if (currentRequestId !== optionalSkillRequestId) return;
      optionalSkillOptions.value = [];
    }
  } finally {
    if (target === 'include') {
      if (currentRequestId === includeSkillRequestId) {
        includeSkillsLoading.value = false;
      }
    } else if (currentRequestId === optionalSkillRequestId) {
      optionalSkillsLoading.value = false;
    }
  }
}

async function loadProfessionSuggestions(value: string): Promise<void> {
  const normalizedValue = value.trim();
  if (normalizedValue.length < 2) {
    professionOptions.value = [];
    professionsLoading.value = false;
    return;
  }

  const currentRequestId = ++professionRequestId;
  professionsLoading.value = true;

  try {
    const suggestions = await getApiClients().search.suggestProfessions(normalizedValue);
    const nextOptions = suggestions.map((item: SkillSuggestion) => item.text);
    if (currentRequestId !== professionRequestId) return;
    professionOptions.value = nextOptions;
  } catch {
    if (currentRequestId !== professionRequestId) return;
    professionOptions.value = [];
  } finally {
    if (currentRequestId === professionRequestId) {
      professionsLoading.value = false;
    }
  }
}

function handleProfessionFilter(
  value: string,
  update: (callbackFn: () => void) => void,
): void {
  void loadProfessionSuggestions(value).then(() => {
    update(() => {
      professionOptions.value = [...professionOptions.value];
    });
  });
}

function handleSkillFilter(
  value: string,
  update: (callbackFn: () => void) => void,
  target: 'include' | 'optional',
): void {
  logSkillDebug('skill-filter-event', {
    target,
    value,
  });
  void loadSkillSuggestions(value, target).then(() => {
    update(() => {
      if (target === 'include') {
        includeSkillOptions.value = [...includeSkillOptions.value];
      } else {
        optionalSkillOptions.value = [...optionalSkillOptions.value];
      }
    });
  });
}
</script>
