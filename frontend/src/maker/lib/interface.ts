export type KeyValueArray = Array<{ [key: string]: any }>

export type DataTable = {
  fields: Array<{
    label: string
    name: string
    unit?: string
    type: string
    options?: Array<{ text: string; value: string }>
    show: boolean
    editable: boolean
    editableHead?: boolean
    errorMessage?: string
    headerError?: boolean
  }>
  items: Array<{ [key: string]: any }>
}
