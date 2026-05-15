/**
 * Admin routes — inspect audit trail, run records, and quality flags.
 */

import { Router, Request, Response } from "express";
import type { AuditStore } from "../services/audit-store.js";

export function adminRouter(store: AuditStore): Router {
  const router = Router();

  // GET /admin/records — list recent run records
  router.get("/records", (req: Request, res: Response) => {
    const limit = Math.min(
      parseInt(req.query.limit as string, 10) || 50,
      200,
    );
    const records = store.getAll(limit);
    res.json({ count: records.length, records });
  });

  // GET /admin/records/:id — get a specific record
  router.get("/records/:id", (req: Request, res: Response) => {
    const record = store.getByRequestId(req.params.id);
    if (!record) {
      res.status(404).json({ error: "Record not found" });
      return;
    }
    res.json(record);
  });

  // POST /admin/flag/:id — mark a record with a quality issue
  router.post("/flag/:id", (req: Request, res: Response) => {
    const { reason } = req.body as { reason?: string };
    if (!reason || typeof reason !== "string" || reason.trim().length === 0) {
      res.status(400).json({ error: "reason is required" });
      return;
    }
    const updated = store.flag(req.params.id, reason.trim());
    if (!updated) {
      res.status(404).json({ error: "Record not found" });
      return;
    }
    res.json({ flagged: true, request_id: req.params.id, reason: reason.trim() });
  });

  return router;
}
