<script setup lang="ts">
import type { FeatureCollection } from 'geojson'

import { reactive, watch } from 'vue'
import embed, { type VisualizationSpec } from 'vega-embed'

import type { KeyValueArray, DataTable } from '../lib/interface'
import spec from '../../assets/template.vg.json' with { type: "json" }
import * as config from '../../common/config'
import * as util from '../lib/util'

var versionSpec = JSON.parse(JSON.stringify(spec)) // copy the template
var visView: any

const props = defineProps<{
  mapColorScheme: string,
  useEqualArea: boolean,
  useInset: boolean
}>()

const state = reactive({
  dataTable: { fields: [], items: [] } as DataTable,
  displayTable: false
})

defineExpose({
  initDataTableWGeojson, updateDataTable, getCSV, validateCSV
})

watch(
  () => props.mapColorScheme,
  (newValue, oldValue) => {
    changeColor(newValue, oldValue)
  }
)

watch(
  () => props.useEqualArea,
  (newValue, oldValue) => {
    state.dataTable.fields[config.COL_AREA].show = props.useEqualArea
  }
)

watch(
  () => props.useInset,
  (newValue, oldValue) => {
    state.dataTable.fields[config.COL_INSET].show = props.useInset
  }
)

function reset() {
  state.dataTable.items = []
  state.dataTable.fields = [
    { label: 'Region', name: 'Region', type: 'text', editable: false, show: true, headerError: false, errorMessage: '' },
    { label: 'RegionLabel', name: 'RegionLabel', type: 'text', editable: true, show: true },
    { label: 'Color', name: 'Color', type: 'color', editable: true, show: false },
    { label: 'ColorGroup', name: 'ColorGroup', type: 'number', editable: false, show: false },
    {
      label: 'Inset',
      name: 'Inset',
      type: 'select',
      options: config.OPTIONS_INSET,
      editable: true,
      show: false
    },
    {
      label: 'Geographic Area',
      name: 'Geographic Area',
      unit: 'sq. km',
      type: 'text',
      editable: true,
      editableHead: true,
      show: true
    }
  ]
  state.displayTable = false
}

function initDataTableWGeojson(geojsonData: FeatureCollection, geojsonRegionCol: string, displayTable: boolean = true) {
  reset()

  document.getElementById('map-vis')!.innerHTML = ''
  state.dataTable.fields.splice(config.NUM_RESERVED_FILEDS)
  state.dataTable.items = []
  state.displayTable = displayTable

  // Transform geojson to data fields
  var geoProperties = util.propertiesToArray(geojsonData)
  if (geoProperties.length === 0) return
  if (!Object.keys(geoProperties[0]).some((key) => key.startsWith('Population')))
    geoProperties = util.addKeyInArray(geoProperties, 'Population (people)', 0)

  const areaKey = Object.keys(geoProperties[0]).find((key) => key.startsWith('Geographic Area'))
  if (areaKey) geoProperties = util.renameKeyInArray(geoProperties, areaKey, 'Geographic Area')
  geoProperties = util.renameKeyInArray(geoProperties, geojsonRegionCol, 'Region')
  geoProperties = util.arrangeKeysInArray(geoProperties, [...config.RESERVE_FIELDS, 'Population (people)'])
  geoProperties.sort((a, b) => a.Region.localeCompare(b.Region))

  versionSpec.data[1].values = geojsonData
  versionSpec.data[2].transform[2].fields = ['properties.' + geojsonRegionCol]

  initDataTableWArray(geoProperties)
}

async function initDataTableWArray(data: KeyValueArray, isReplace = true) {
  data = util.filterKeyValueInArray(data, config.RESERVE_FIELDS)
  if (isReplace) {
    state.dataTable.items = data
  } else {
    state.dataTable.items = util.mergeObjInArray(state.dataTable.items, data, 'Region')
  }

  var keys = Object.keys(state.dataTable.items[0])
  for (var i = 0; i < keys.length; i++) {
    if (!config.RESERVE_FIELDS.includes(keys[i])) {
      var [fieldname, unit] = util.getNameUnit(keys[i])
      state.dataTable.fields.push({ label: keys[i], name: fieldname, unit: unit, type: 'number', editable: true, editableHead: true, show: true })
    }
  }

  versionSpec.data[0].values = state.dataTable.items
  versionSpec.data[0].format = 'json'

  let container = await embed('#map-vis', <VisualizationSpec>versionSpec, { renderer: 'svg', actions: false })
  visView = container.view
  if (props.mapColorScheme !== 'custom') visView.signal('colorScheme', props.mapColorScheme).runAsync()
}

function validateCSV(csvData: KeyValueArray): boolean {
  if (csvData.length === 0) return false;

  // 1. Check if the CSV header contains the "Region" column.
  if (!csvData[0].hasOwnProperty("Region")) {

    // Mark error on the header for the Region field.
    const regionField = state.dataTable.fields.find(field => field.label === "Region");
    if (regionField) {
      regionField.errorMessage = "Region column not found in the uploaded CSV";
      regionField.headerError = true; // Custom property for header errors.
    }
    return false;
  } else {

    // Clear any header error if the Region column is present.
    const regionField = state.dataTable.fields.find(field => field.label === "Region");
    if (regionField) {
      regionField.errorMessage = "";
      regionField.headerError = false;
    }
  }

  // 2. Compare Region values row by row.
  const csvRegions = csvData.map(row => row["Region"]);
  const mapRegions = state.dataTable.items.map(row => row["Region"]);

  let valid = true;

  // Check row count mismatch and mark header error.
  if (csvRegions.length !== mapRegions.length) {
    const regionField = state.dataTable.fields.find(field => field.label === "Region");
    if (regionField) {
      regionField.errorMessage = `Row count mismatch: CSV has ${csvRegions.length} rows, but expected ${mapRegions.length}`;
      regionField.headerError = true;
    }
    valid = false;
  }

  // Now, check each row's Region value.
  for (let i = 0; i < Math.min(csvRegions.length, mapRegions.length); i++) {
    if (csvRegions[i] !== mapRegions[i]) {

      // Mark error on the specific row's Region cell.
      state.dataTable.items[i].regionError = `Region mismatch at row ${i + 1}: CSV has "${csvRegions[i]}", expected "${mapRegions[i]}"`;
      valid = false;
    } else {

      // Clear any previous error if the values match.
      delete state.dataTable.items[i].regionError;
    }
  }

  return valid;
}

function updateDataTable(csvData: KeyValueArray) {
  if (csvData.length === 0) return

  const areaKey = Object.keys(csvData[0]).find((key) => key.startsWith('Geographic Area'))
  if (areaKey) {
    var [fieldname, unit] = util.getNameUnit(areaKey)
    state.dataTable.fields[config.COL_AREA].unit = unit
    csvData = util.renameKeyInArray(csvData, areaKey, 'Geographic Area')
  }

  state.dataTable.items = util.filterKeyValueInArray(state.dataTable.items, config.RESERVE_FIELDS, null)
  state.dataTable.fields.splice(config.NUM_RESERVED_FILEDS)
  state.dataTable.fields[config.COL_COLOR].show = csvData[0].hasOwnProperty('Color')
  state.dataTable.fields[config.COL_AREA].show = csvData[0].hasOwnProperty('Geographic Area')
  state.dataTable.fields[config.COL_INSET].show = csvData[0].hasOwnProperty('Inset')
  initDataTableWArray(csvData, false)

  return {
    customColor: state.dataTable.fields[config.COL_COLOR].show,
    useEqualArea: state.dataTable.fields[config.COL_AREA].show,
    useInset: state.dataTable.fields[config.COL_INSET].show
  }
}

function changeColor(scheme: string, oldScheme: string) {
  if (scheme === 'custom') {
    if (oldScheme !== 'custom') {
      // No color assigned - Copy all color from Vega to data table
      let colorScale = visView.scale('color_group')
      for (let i = 0; i < state.dataTable.items.length; i++) {
        state.dataTable.items[i]['Color'] = colorScale(state.dataTable.items[i]['ColorGroup'])
      }
    } else {
      // Assign white to empty color
      for (let i = 0; i < state.dataTable.items.length; i++) {
        state.dataTable.items[i]['Color'] = state.dataTable.items[i]['Color'] ? state.dataTable.items[i]['Color'] : '#ffffff'
      }
    }

    state.dataTable.fields[config.COL_COLOR].show = true
  } else {
    for (let i = 0; i < state.dataTable.items.length; i++) {
      delete state.dataTable.items[i]['Color']
    }

    state.dataTable.fields[config.COL_COLOR].show = false
    visView.signal('colorScheme', scheme).runAsync()
  }
}

async function getCSV(isGetFile = false) {
  return await util.getGeneratedCSV(state.dataTable, isGetFile)
}

function onValueChange(rIndex: number, label: string, event: Event) {
  const target = <HTMLInputElement>event.target
  state.dataTable.items[rIndex][label] = target.value
  const changeset = visView.changeset().modify((item: any) => item.Region === state.dataTable.items[rIndex].Region, label, target.value)
  visView.change('source_csv', changeset).run()
}
</script>
<template>
  <div class="card w-75 m-2 border-0">
    <!-- Overview Message -->
    <div class="p-2">
      <span class="badge text-bg-secondary">Input Overview</span>
    </div>
    <div class="p-2" v-if="state.dataTable.items.length < 1">
      <p>Please follow steps on the left panel.</p>
      <p>
        Don't know where to start? You may try editing one of our
        <a href="/cartogram">examples</a>. If you have any questions or issues about cartogram
        generation, refer to the
        <a href="/faq">Frequently Asked Questions</a> or
        <a href="/contact">Contact us</a>.
      </p>
    </div>

    <!-- Map Container -->
    <div id="map-vis" class="vis-area p-2"></div>

    <!-- Data Table -->
    <div class="d-table p-2" v-if="state.displayTable && state.dataTable.items.length > 0">
      <table class="table table-bordered">
        <thead>
          <tr class="table-light">
            <th v-for="(field, index) in state.dataTable.fields" v-show="field.show" :key="index">
              <!-- Wrap header content in a container for tooltip -->
              <div class="header-cell" :class="{ 'header-error': field.label === 'Region' && field.headerError }">
                <span v-if="!field.editableHead">{{ field.label }}</span>
                <div v-else>
                  <i v-if="state.dataTable.fields[index].name !== 'Geographic Area'"
                    class="position-absolute top-0 end-0 btn-icon text-secondary fas fa-minus-circle"
                    @click="state.dataTable.fields[index].show = false"
                    :title="'Remove ' + state.dataTable.fields[index].name + ' column'"></i>
                  <!-- TODO ask for the confirmation and completely remove it so it'll beremove from the popup. -->
                  <input class="form-control" v-model="state.dataTable.fields[index].name" :type="field.name"
                    placeholder="Data name" />
                  <input class="form-control" v-model="state.dataTable.fields[index].unit" :type="field.unit"
                    placeholder="Unit" />
                </div>
                <!-- Tooltip for header error -->
                <div v-if="field.label === 'Region' && field.headerError" class="tooltip">
                  {{ field.errorMessage }}
                </div>
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, rIndex) in state.dataTable.items" :key="rIndex">
            <td v-for="(field, index) in state.dataTable.fields" v-show="field.show" :key="index">
              <!-- Wrap cell content in a container for tooltip -->
              <div class="cell-content" :class="{ 'error-cell': field.label === 'Region' && row.regionError }">
                <span v-if="!field.editable">{{ row[field.label] }}</span>
                <select v-else-if="field.type === 'select'" class="form-control"
                  v-model="state.dataTable.items[rIndex][field.label]">
                  <option v-for="option in field.options" :key="option.value" :value="option.value">
                    {{ option.text }}
                  </option>
                </select>
                <input v-else-if="field.show" class="form-control" :type="field.type" :value="row[field.label]"
                  @change="($event) => onValueChange(rIndex, field.label, $event)" />
                <!-- Tooltip for cell error -->
                <div v-if="field.label === 'Region' && row.regionError" class="tooltip">
                  {{ row.regionError }}
                </div>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.vis-area {
  width: 100%;
  height: 300px;
}

/* Table input/select styling */
table input,
table select {
  width: 100%;
  min-width: 100px;
}

table input[type='color'] {
  padding: 0;
  min-width: 60px;
}

.btn-icon {
  cursor: pointer;
}

/* Header error highlighting */
.header-error {
  background-color: #f8d7da;
  /* Light red background */
}

/* Cell error highlighting */
.error-cell {
  background-color: #f8d7da;
}

/* Tooltip container styles */
.header-cell,
.cell-content {
  position: relative;
  display: inline-block;
}

/* Tooltip styling */
.tooltip {
  visibility: hidden;
  background-color: #333;
  color: #fff;
  text-align: left;
  padding: 4px;
  border-radius: 4px;
  position: absolute;
  z-index: 10;
  left: 100%;
  top: 50%;
  transform: translateY(-50%);
  white-space: nowrap;
  opacity: 0;
  transition: opacity 0s;
}

/* Show tooltip immediately on hover */
.header-cell:hover .tooltip,
.cell-content:hover .tooltip {
  visibility: visible;
  opacity: 1;
  transition: opacity 0s;
}
</style>
