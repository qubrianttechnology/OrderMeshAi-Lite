export const wholesaleCategories = [
  {
    value: "electronics",
    label: "Electronics",
    examples: "Phone accessories, chargers, earphones and cables",
  },
  {
    value: "fashion",
    label: "Fashion",
    examples: "T-shirts, shirts, trousers and shoes",
  },
  {
    value: "beauty",
    label: "Beauty",
    examples: "Cosmetics, skincare and perfumes",
  },
  {
    value: "grocery",
    label: "Grocery",
    examples: "Rice, sugar, dhal, spices and snacks",
  },
  {
    value: "household",
    label: "Household",
    examples: "Kitchen items, plastic products and cleaning supplies",
  },
  {
    value: "packaging",
    label: "Packaging",
    examples: "Shopping bags, food containers and boxes",
  },
  {
    value: "stationery",
    label: "Stationery",
    examples: "Books, pens, files and office supplies",
  },
  {
    value: "hardware",
    label: "Hardware",
    examples: "Electrical items, tools and plumbing accessories",
  },
  {
    value: "vehicle_parts",
    label: "Vehicle parts",
    examples: "Car, van, motorcycle and commercial vehicle spare parts",
  },
  {
    value: "other",
    label: "Other / mixed categories",
    examples: "A mixed wholesale or distribution catalog",
  },
] as const;

export function categoryLabel(value?: string) {
  return (
    wholesaleCategories.find((item) => item.value === value)?.label ||
    "Other / mixed categories"
  );
}
