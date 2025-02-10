<script setup lang="ts">
import * as d3 from 'd3'
import type { FeatureCollection } from 'geojson'
import { Toast, Modal } from 'bootstrap'
import { reactive, ref, onMounted } from 'vue'

import * as util from '../lib/util'
import HTTP from '../lib/http'
import type { KeyValueArray } from '../lib/interface'
import type { MapHandlers } from '../../common/interface'

import CFormGeojson from './CFormGeojson.vue'
import CFormCsv from './CFormCsv.vue'
import CSelectColor from './CSelectColor.vue'
import CDataTable from './CDataTable.vue'

var mapDBKey = util.generateShareKey(32)
const dataTableEl = ref()

const props = defineProps<{
  maps: MapHandlers
  mapName?: string
  mapTitle?: string
  mapColorScheme?: string
  geoUrl?: string
  csvUrl?: string
}>()

const state = reactive({
  loadingProgress: 0,
  error: '',
  title: props.mapTitle ? props.mapTitle : '',
  handler: props.mapName ? props.mapName : '',
  geojsonData: {} as FeatureCollection,
  geojsonRegionCol: '',
  csvFile: '',
  colorScheme: props.mapColorScheme ? props.mapColorScheme : 'pastel1',
  useEqualArea: true,
  useInset: false
})

onMounted(() => {
  if (!props.mapName || !props.geoUrl || !props.csvUrl) return

  HTTP.get(props.geoUrl).then(function (response: any) {
    onGeoJsonChanged(props.mapName!, response, 'Region', props.csvUrl)
  })
})

function onGeoJsonChanged(
  handler: string,
  geojsonData: FeatureCollection,
  regionCol: string,
  csvFile = '',
  displayTable : boolean = true
) {
  state.handler = handler
  state.geojsonData = geojsonData
  state.geojsonRegionCol = regionCol
  state.csvFile = csvFile
  dataTableEl.value.initDataTableWGeojson(geojsonData, regionCol, displayTable)

  // Immediately populate data if a CSV file is supplied
  if (csvFile) {
    d3.csv(csvFile)
      .then((csvData) => {
        if (!csvData || !Array.isArray(csvData)) {
          console.error('Invalid CSV data')
          return
        }
        onCsvUpdate(csvData)
      })
      .catch((error) => {
        console.error('Error loading CSV:', error)
      })
  }
}

async function onCsvBtnClick() {
  await dataTableEl.value.getCSV(true)
}

function onCsvUpdate(csvData: KeyValueArray) {
  let isCSVValid = dataTableEl.value.validateCSV(csvData);

  // Do not update the data table if the CSV is invalid
  if (!isCSVValid) {
    return
  }
  const updatedProps = dataTableEl.value.updateDataTable(csvData)
  state.colorScheme = updatedProps.customColor ? 'custom' : state.colorScheme
  state.useEqualArea = updatedProps.useEqualArea
  state.useInset = updatedProps.useInset
}

async function getGeneratedCartogram() {
  const progressModal = new Modal('#progressBackdrop', {
    backdrop: 'static',
    keyboard: false
  })
  progressModal.show()

  var csvData = await dataTableEl.value.getCSV()

  await new Promise<any>(function (resolve, reject) {
    var req_body =
      'data=' +
      JSON.stringify({
        title: state.title,
        scheme: state.colorScheme,
        handler: state.handler,
        csv: csvData,
        geojsonRegionCol: state.geojsonRegionCol,
        mapDBKey: mapDBKey,
        persist: true,
        editedFrom: props.geoUrl
      })

    var progressUpdater = window.setInterval(
      (function (key) {
        return function () {
          HTTP.get(
            '/api/v1/getprogress?key=' + encodeURIComponent(key) + '&time=' + Date.now()
          ).then(function (progress: any) {
            if (progress.progress === null) {
              state.loadingProgress = 8
              return
            }

            state.loadingProgress = Math.floor(progress.progress * 100)
            // state.error += progress.stderr
            console.log(progress.stderr)
          })
        }
      })(mapDBKey),
      500
    )

    HTTP.post('/api/v1/cartogram', req_body, {
      'Content-type': 'application/x-www-form-urlencoded'
    }).then(
      function (response: any) {
        state.loadingProgress = 100
        window.clearInterval(progressUpdater)
        resolve(response)
        window.location.href = '/cartogram/key/' + response.mapDBKey + '/preview'
      },
      function (error: any) {
        state.loadingProgress = 100
        window.clearInterval(progressUpdater)
        reject(error)
      }
    )
  }).catch(function (error: any) {
    state.error = error
    progressModal.hide()
    Toast.getOrCreateInstance(document.getElementById('errorToast')!).show()
    return
  })
}
</script>

<template>
  <div class="d-flex flex-fill">
    <div class="card w-25 m-2">
      <c-form-geojson
        v-bind:mapDBKey="mapDBKey"
        v-bind:maps="props.maps"
        v-bind:geoUrl="props.geoUrl"
        v-on:changed="onGeoJsonChanged"
      />

      <div class="p-2">
        <div class="badge text-bg-secondary">2. Specify visualization</div>

        <div class="p-2">
          Title
          <input class="form-control" type="text" v-model="state.title" maxlength="100" />
        </div>

        <div class="p-2">
          <c-select-color
            v-bind:key="state.colorScheme"
            v-bind:disabled="!('features' in state.geojsonData)"
            v-bind:scheme="state.colorScheme"
            v-on:changed="(scheme) => (state.colorScheme = scheme)"
          />
        </div>

        <div class="p-2">
          <div class="form-check">
            <input
              class="form-check-input"
              type="checkbox"
              v-model="state.useEqualArea"
              v-bind:disabled="!('features' in state.geojsonData)"
              id="chk-area"
            />
            <label class="form-check-label" for="chk-area">
              Include geographic area (recommended)
            </label>
          </div>
          <div class="form-check">
            <input
              class="form-check-input"
              type="checkbox"
              v-model="state.useInset"
              v-bind:disabled="!('features' in state.geojsonData)"
              id="chk-inset"
            />
            <label class="form-check-label" for="chk-inset"> Define inset </label>
          </div>
        </div>
      </div>

      <div class="p-2">
        <div class="badge text-bg-secondary">3. Download data (optional)</div>
        <div class="p-2">
          <button
            class="btn btn-outline-secondary"
            v-bind:disabled="!('features' in state.geojsonData)"
            v-on:click="onCsvBtnClick"
          >
            Download data
          </button>
          for editing on your device.
        </div>
      </div>

      <c-form-csv v-bind:disabled="!('features' in state.geojsonData)" v-on:changed="onCsvUpdate" />

      <div class="p-2">
        <div class="badge text-bg-secondary">5. Generate cartogram</div>

        <div class="row p-2">
          <div class="col-auto p-2">
            <p class="bg-warning-subtle p-1 rounded">
              <span class="badge text-bg-warning">Important</span> The data will be pruned from our
              server within 1-2 days, unless you share and access a non-preview link. We strongly
              advise you to back up your original data in a safe place so you can regenerate the
              cartogram if needed.
            </p>
            <button class="btn btn-primary" v-on:click="getGeneratedCartogram">Generate</button>
          </div>
        </div>
      </div>
    </div>

    <c-data-table
      ref="dataTableEl"
      v-bind:mapColorScheme="state.colorScheme"
      v-bind:useEqualArea="state.useEqualArea"
      v-bind:useInset="state.useInset"
    />
  </div>

  <div
    id="errorToast"
    class="toast toast position-fixed end-0 bottom-0 m-3 text-bg-danger"
    role="alert"
    aria-live="assertive"
    aria-atomic="true"
    data-bs-autohide="false"
  >
    <div class="d-flex">
      <div class="toast-body">{{ state.error }}</div>
      <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>
  </div>

  <div class="modal" id="progressBackdrop" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-body">
          <div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100">
            <div
              class="progress-bar bg-primary"
              :style="{ width: state.loadingProgress + '%' }"
            ></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
