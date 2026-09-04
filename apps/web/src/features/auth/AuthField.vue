<script setup lang="ts">
import { computed, ref } from "vue";

type FieldType = "email" | "password" | "text";

const props = withDefaults(
  defineProps<{
    id: string;
    label: string;
    modelValue: string;
    type?: FieldType;
    autocomplete?: string;
    placeholder?: string;
    inputmode?: "email" | "numeric" | "text";
    maxlength?: number;
    minlength?: number;
    disabled?: boolean;
    required?: boolean;
    error?: string;
    hint?: string;
    actionLabel?: string;
    actionBusyLabel?: string;
    actionBusy?: boolean;
    actionDisabled?: boolean;
  }>(),
  {
    type: "text",
    autocomplete: "off",
    placeholder: "",
    inputmode: "text",
    maxlength: undefined,
    minlength: undefined,
    disabled: false,
    required: false,
    error: "",
    hint: "",
    actionLabel: "",
    actionBusyLabel: "",
    actionBusy: false,
    actionDisabled: false,
  },
);

const emit = defineEmits<{
  (event: "update:modelValue", value: string): void;
  (event: "focus"): void;
  (event: "blur"): void;
  (event: "action"): void;
}>();

const focused = ref(false);
const hasValue = computed(() => props.modelValue.length > 0);
const hasAction = computed(() => Boolean(props.actionLabel));

function updateValue(event: Event): void {
  emit("update:modelValue", (event.target as HTMLInputElement).value);
}

function focusField(): void {
  focused.value = true;
  emit("focus");
}

function blurField(): void {
  focused.value = false;
  emit("blur");
}
</script>

<template>
  <div
    class="auth-field"
    :class="{
      'is-focused': focused,
      'has-value': hasValue,
      'has-error': Boolean(error),
      'has-action': hasAction,
    }"
  >
    <div class="auth-field-control">
      <input
        :id="id"
        :value="modelValue"
        :type="type"
        :autocomplete="autocomplete"
        :placeholder="focused || hasValue ? placeholder : ' '"
        :inputmode="inputmode"
        :maxlength="maxlength"
        :minlength="minlength"
        :disabled="disabled"
        :required="required"
        :aria-invalid="Boolean(error)"
        :aria-describedby="error ? `${id}-error` : hint ? `${id}-hint` : undefined"
        @input="updateValue"
        @focus="focusField"
        @blur="blurField"
      />
      <label :for="id">{{ label }}</label>
      <button
        v-if="hasAction"
        class="auth-field-action"
        type="button"
        :disabled="disabled || actionDisabled || actionBusy"
        @mousedown.prevent
        @click="emit('action')"
      >
        <span v-if="actionBusy" class="auth-spinner auth-spinner-small" aria-hidden="true"></span>
        {{ actionBusy ? actionBusyLabel || actionLabel : actionLabel }}
      </button>
    </div>
    <Transition name="auth-field-error">
      <p v-if="error" :id="`${id}-error`" class="auth-field-error" role="alert">
        {{ error }}
      </p>
    </Transition>
    <p v-if="hint && !error" :id="`${id}-hint`" class="auth-field-hint">{{ hint }}</p>
  </div>
</template>
