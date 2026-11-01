export type DashboardPreferences = {
  layout?: "recommended" | "full";
  full_business_tools?: boolean;
  modules: string[];
  customized: boolean;
  service_business: boolean;
  customer_label: string;
  catalog_label: string;
  request_label: string;
};
export type ServiceSummary = {
  total: number;
  pending_review: number;
  accepted: number;
  completed: number;
};
export type Organization = {
  id: string;
  name: string;
  role: "owner" | "admin" | "staff" | "viewer";
  plan: string;
  subscription_status: string;
  monthly_order_limit: number;
  business_type: string;
  dashboard?: DashboardPreferences;
  business_profile: Record<string, string>;
  trial_ends_at: string | null;
  paid_until: string | null;
};
export type User = {
  phone?: string;
  has_photo?: boolean;
  id: string;
  name: string;
  email: string;
  organizations: Organization[];
};
export type Customer = {
  credit_limit_minor?: number;
  payment_terms_days?: number;
  price_group?: string;
  id: string;
  name: string;
  phone: string;
  address: string;
  active: boolean;
};
export type Product = {
  barcode?: string;
  cost_minor?: number | null;
  wholesale_price_minor?: number | null;
  wholesale_min_qty?: number;
  min_order_qty?: number;
  category?: string;
  track_stock: boolean;
  id: string;
  name: string;
  sku: string;
  aliases: string[];
  unit: string;
  price_minor: number;
  stock: number;
  reorder_level: number;
  active: boolean;
};
export type Order = {
  id: string;
  customer_id: string;
  customer_name: string;
  status: "confirmed" | "fulfilled" | "cancelled";
  total_minor: number;
  created_at: string;
  draft_id: string | null;
};
export type Analytics = {
  sales_minor: number;
  order_count: number;
  pending_orders: number;
  pending_approvals?: number;
  low_stock_count: number;
  customer_count: number;
  daily_sales: { date: string; total_minor: number }[];
};
export type Draft = {
  id: string;
  source_text: string;
  result: {
    kind?: "service_request";
    source_type?: "image_text" | "voice_transcript";
    service_request?: ServiceFields;
    missing_fields?: string[];
    review?: {
      status: string;
      revision: number;
      fields: ServiceFields | null;
      notes: string;
    };
    provider: string;
    language: string;
    flags: string[];
    delivery_instructions: string | null;
    items: {
      source: string;
      product_id: string | null;
      product_name: string | null;
      quantity: number | null;
      unit: string | null;
      confidence: number;
      flags: string[];
    }[];
  };
};
export type Audit = {
  id: string;
  action: string;
  entity_id: string;
  created_at: string;
};
export type InboxPhoneNumber = {
  id: string;
  phone_number_id: string;
  display_phone_number: string;
  active: boolean;
};
export type InboxConversation = {
  archived: boolean;
  pinned: boolean;
  id: string;
  customer_phone: string;
  customer_name: string;
  customer_id: string | null;
  customer_match_source:
    "unmatched" | "customer_phone" | "whatsapp_contact" | "manual";
  last_message_preview: string;
  last_message_at: string;
  unread_count: number;
};
export type InboxMessage = {
  category: string;
  category_reason: string;
  category_reviewed: boolean;
  id: string;
  direction: "inbound" | "outbound";
  message_type: string;
  transcription_status?: "" | "pending" | "transcribed" | "failed";
  transcription_error?: string;
  text: string | null;
  sent_at: string;
  extraction_draft_id: string | null;
  delivery_status: "accepted" | "sent" | "delivered" | "read" | "failed" | null;
  delivery_error_code: string;
  is_simulated: boolean;
};

export type ServiceFields = {
  request_type: "project" | "quotation" | "appointment" | "support" | "service";
  requirements: string[];
  budget: string | null;
  deadline: string | null;
  appointment: string | null;
  contact: string | null;
};

export type PendingWhatsAppOrder = {
  draft: Draft;
  customer_name: string;
  customer_phone: string;
  is_simulated?: boolean;
  availability: {
    product_id: string | null;
    product_name: string;
    quantity: number | null;
    unit: string | null;
    status: string;
  }[];
  created_at: string;
};
