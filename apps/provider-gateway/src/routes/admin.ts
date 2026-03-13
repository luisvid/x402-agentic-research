/**
 * Admin routes — inspect audit trail and run records.
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

  return router;
}
