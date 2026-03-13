import { Request, Response, NextFunction } from "express";
import { logger } from "../index.js";

export function errorHandler(
  err: Error,
  req: Request,
  res: Response,
  _next: NextFunction,
): void {
  const requestId = req.headers["x-request-id"] as string;
  logger.error({ err, requestId }, "Unhandled error");
  res.status(500).json({
    error: "Internal server error",
    request_id: requestId,
  });
}
