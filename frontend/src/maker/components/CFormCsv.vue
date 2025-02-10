<script setup lang="ts">
import * as d3 from 'd3'
import * as XLSX from 'xlsx'
import { ref } from 'vue';

import * as util from '../lib/util'

const selectedFileName = ref('');

const props = withDefaults(
  defineProps<{
    disabled: boolean
  }>(),
  {
    disabled: false
  }
)

const emit = defineEmits(['changed'])

async function uploadCsvData(event: Event) {
  // TODO check region values as well as color and inset format
  const input = event.target as HTMLInputElement;
  const files = input.files;
  if (!files || files.length === 0) return;

  // Store the file name before clearing
  selectedFileName.value = files[0].name;

  const data = await util.readFile(files[0]);
  const type = files[0].name.split('.').pop()?.slice(0, 3);
  let csvData: any[] = [{}];

  if (type === 'xls' || type === 'xlsx') {
    const wb = XLSX.read(data, { type: 'binary' });
    const ws = wb.Sheets[wb.SheetNames[0]];
    csvData = XLSX.utils.sheet_to_json(ws);
  } else {
    csvData = d3.csvParse(data as string);
  }

  if (!csvData || csvData.length < 1) return;

  //   if (csvData.some((obj) => obj.hasOwnProperty('Region'))) {
  //     state.csvRegionCol = 'Region'
  //   }
  //   console.log(state.csvData)
  
  // Reset the file input so that selecting the same file again triggers a change event.
  input.value = '';

  emit('changed', csvData)
}
</script>

<template>
  <div class="p-2 text-bg-light">
    <div class="badge text-bg-secondary">4. Input your data</div>
    <div class="p-2">Input your data to the table on the right panel.</div>
    <div class="p-2">
      Alternatively, upload your data in CSV or Excel format. <br>
      <label for="csvInput" class="custom-file-upload">
        Choose file
      </label>
      <input
        id="csvInput"
        type="file"
        accept="text/csv,.csv,.xlsx,.xls"
        :disabled="props.disabled"
        @change="uploadCsvData"
      />
      <div v-if="selectedFileName">
        <strong>Selected file:</strong> {{ selectedFileName }}
      </div>
    </div>
  </div>
</template>
<style scoped>

/* Hide the default file input */
input[type="file"] {
  display: none;
}

.custom-file-upload {
  border: 1px solid #ccc;
  display: inline-block;
  padding: 6px 12px;
  cursor: pointer;
  border-radius: 4px;
  transition: background-color 0.2s ease;
}

.custom-file-upload:hover {
  background-color: #e7e7e9;
}
</style>

