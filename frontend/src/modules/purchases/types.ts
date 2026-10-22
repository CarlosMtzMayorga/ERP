export interface TopSupplierMetric {
  supplier_id: string;
  legal_name: string;
  rfc: string;
  total_purchased: number;
  orders_count: number;
}

export interface PurchasesDashboardMetrics {
  monthly_purchases_total: number;
  pending_purchase_orders_count: number;
  unpaid_invoices_balance: number;
  active_suppliers_count: number;
  top_suppliers: TopSupplierMetric[];
}

export interface PurchaseDocumentItem {
  id: string;
  product_id: string;
  line_number: number;
  sku: string;
  description: string;
  quantity_ordered: number;
  quantity_received: number;
  unit_cost: number;
  discount_amount: number;
  freight_prorated: number;
  effective_unit_cost: number;
  subtotal: number;
  vat_rate: number;
  vat_amount: number;
  total: number;
  source_item_id?: string;
}

export interface PurchaseDocument {
  id: string;
  branch_id: string;
  warehouse_id: string;
  supplier_id: string;
  currency_id: string;
  document_type: 'REQUISICION' | 'ORDEN_COMPRA' | 'RECEPCION' | 'FACTURA_PROVEEDOR';
  status: 'BORRADOR' | 'AUTORIZADA' | 'PARCIALMENTE_RECIBIDA' | 'RECIBIDA' | 'FACTURADA' | 'CANCELADA';
  serie: string;
  folio: number;
  formatted_folio: string;
  issue_date: string;
  expected_date?: string;
  source_document_id?: string;
  source_document_type?: string;
  cfdi_uuid?: string;
  subtotal: number;
  discount_total: number;
  freight_total: number;
  tax_iva_total: number;
  total: number;
  notes?: string;
  supplier_name?: string;
  supplier_rfc?: string;
  items: PurchaseDocumentItem[];
}

export interface PayableDocument {
  id: string;
  supplier_id: string;
  branch_id: string;
  purchase_document_id?: string;
  document_type: string;
  serie?: string;
  folio?: number;
  formatted_folio: string;
  cfdi_uuid?: string;
  issue_date: string;
  due_date: string;
  credit_days: number;
  original_total: number;
  original_subtotal: number;
  original_vat: number;
  current_balance: number;
  currency_code: string;
  status: 'PENDIENTE' | 'PARCIAL' | 'LIQUIDADO' | 'CANCELADO';
  supplier_name?: string;
  supplier_rfc?: string;
}

export interface XMLConceptPreview {
  clave_prod_serv: string;
  no_identificacion?: string;
  cantidad: number;
  clave_unidad: string;
  unidad?: string;
  descripcion: string;
  valor_unitario: number;
  importe: number;
  descuento: number;
  objeto_imp: string;
  iva_importe: number;
  iva_tasa: number;
  matched_product_id?: string;
  matched_sku?: string;
}

export interface XMLInvoicePreview {
  uuid: string;
  serie?: string;
  folio?: string;
  fecha: string;
  forma_pago?: string;
  metodo_pago?: string;
  moneda: string;
  tipo_cambio: number;
  subtotal: number;
  descuento: number;
  total_iva: number;
  total_retenciones: number;
  total: number;
  emisor_rfc: string;
  emisor_nombre: string;
  emisor_regimen?: string;
  receptor_rfc: string;
  supplier_exists: boolean;
  supplier_id?: string;
  supplier_credit_days: number;
  concepts: XMLConceptPreview[];
}

