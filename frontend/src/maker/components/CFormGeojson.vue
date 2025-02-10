<script setup lang="ts">
import type { FeatureCollection } from 'geojson'
import { ref, reactive } from 'vue'

import HTTP from '../lib/http'
import type { MapHandlers } from '../../common/interface'

const props = defineProps<{
  mapDBKey: string
  maps: MapHandlers
  geoUrl?: string
}>()

const emit = defineEmits(['changed'])
const fileEl = ref()
var geojsonData = {} as FeatureCollection

const state = reactive({
  isLoading: false,
  error: '',
  handler: '',
  geojsonUniqueProperties: [] as Array<string>,
  geojsonRegionCol: ''
})

async function loadGeoJson(event: Event) {
  fileEl.value.value = null
  geojsonData = {} as FeatureCollection
  state.geojsonUniqueProperties = []
  if (!state.handler) return

  var basedUrl = '/static/cartdata/' + state.handler
  HTTP.get(basedUrl + '/Geographic Area.json').then(function (response: any) {
    state.geojsonRegionCol = 'Region'
    emit('changed', state.handler, response, state.geojsonRegionCol, basedUrl + '/data.csv')
  })
}

async function uploadGeoJson(event: Event) {
  geojsonData = {} as FeatureCollection
  state.geojsonUniqueProperties = []
  const files = (event.target as HTMLInputElement).files
  if (!files || files.length == 0) return

  state.isLoading = true
  const formData = new FormData()
  formData.append('file', files[0])

  var response = await new Promise<any>(function (resolve, reject) {
    HTTP.post('/api/v1/cartogram/preprocess/' + props.mapDBKey, formData).then(
      function (response: any) {
        resolve(response)
      },
      function (error: any) {
        reject(error)
      }
    )
  }).catch(function (error: any) {
    console.log(error)
    state.error = 'Unable to processs your geospatial file(s)'
    state.isLoading = false
    return
  })

  if (!response || !response.geojson) return
  var geojson = response.geojson
  // Check whether the GeoJSON contains any polygons or multipolygons and remove all other objects.
  if (!geojson || !geojson.features) {
    state.error = 'Invalid geospatial file'
    state.isLoading = false
    return
  }

  state.error = ''
  geojsonData = geojson
  state.geojsonUniqueProperties = response.unique
  state.geojsonRegionCol = ''
  state.handler = 'custom'
  state.isLoading = false
  const firstUniqueProprety = state.geojsonUniqueProperties[0]
  emit('changed', state.handler, geojsonData, firstUniqueProprety, '', false)
}
</script>

<template>
  <div class="p-2 text-bg-light">
    <div class="badge text-bg-secondary">1. Define a map</div>
    <!-- TODO allow creating cartogram by url? -->
    <div v-if="props.geoUrl" class="p-2">
      <input type="text" v-bind:value="props.geoUrl" disabled />
    </div>
    <div v-else>
      <div class="p-2">
        Select an appropriate map for your data.

        <select class="form-select" v-model="state.handler" v-on:change="loadGeoJson">
          <option></option>
          <option v-for="(mapItem, mapKey) in props.maps" v-bind:value="mapKey">
            {{ mapItem.name }}
          </option>
        </select>
      </div>
      <div class="p-2">
        OR upload your GeoJSONs or Shapefiles (.shp, .shx, and .dbf in zip).
        <input
          ref="fileEl"
          class="form-control"
          v-bind:class="{ 'is-invalid': state.error }"
          type="file"
          accept=".geojson,.json,.zip"
          v-on:change="uploadGeoJson"
        />
        <div class="invalid-feedback">{{ state.error }}</div>
      </div>
      <div class="d-flex justify-content-center" v-if="state.isLoading">
        <div class="p-2 spinner-border" role="status">
          <span class="visually-hidden">Loading...</span>
        </div>
      </div>
      <div class="p-2" v-if="state.geojsonUniqueProperties.length > 0">
        Which property contain unique region names (e.g., country names)?
        <select
          class="form-select"
          v-model="state.geojsonRegionCol"
          v-on:change="emit('changed', state.handler, geojsonData, state.geojsonRegionCol)"
        >
          <option v-for="(item, index) in state.geojsonUniqueProperties">
            {{ item }}
          </option>
        </select>
      </div>
    </div>
  </div>
</template>
