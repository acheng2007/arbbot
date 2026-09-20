import Link from "next/link";
import { Button } from "@/components/ui/button";
export default function NotFound() {
  return (
    <section>
      <h1 className="text-3xl font-semibold">Page not found</h1>
      <p className="my-5 text-muted-foreground">This view is not available.</p>
      <Button asChild>
        <Link href="/">Back to overview</Link>
      </Button>
    </section>
  );
}
