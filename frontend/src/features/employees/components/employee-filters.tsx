import { Search } from "lucide-react";
import Form from "next/form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import type { AvailabilityStatus } from "@/lib/api/types";

import { AVAILABILITY } from "../labels";

/**
 * Search + availability filter as a GET form (Next.js <Form>).
 * Submitting changes the URL to /employees?q=python&availability=available; the page reads the URL.
 * <Form> from next/form makes that a fast client-side navigation (and prefetches the result page's
 * shell); without JavaScript it is still a normal HTML form that works.
 */
export function EmployeeFilters({ search, availability }: { search?: string; availability?: AvailabilityStatus }) {
  return (
    <Form action="/employees" className="flex flex-wrap items-end gap-3" role="search">
      <div className="min-w-56 flex-1 space-y-1.5">
        <Label htmlFor="employee-search">Search</Label>
        <Input
          id="employee-search"
          name="q"
          type="search"
          placeholder="Code, name, department or location"
          defaultValue={search}
          maxLength={100}
        />
      </div>
      <div className="w-48 space-y-1.5">
        <Label htmlFor="employee-availability">Availability</Label>
        <NativeSelect id="employee-availability" name="availability" defaultValue={availability ?? ""}>
          <option value="">Anyone</option>
          {AVAILABILITY.map((a) => (
            <option key={a.value} value={a.value}>
              {a.label}
            </option>
          ))}
        </NativeSelect>
      </div>
      <Button type="submit">
        <Search aria-hidden /> Search
      </Button>
    </Form>
  );
}
