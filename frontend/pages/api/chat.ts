import type { NextApiRequest, NextApiResponse } from "next";

const LAMBDA_URL = process.env.LAMBDA_URL!;
const API_KEY = process.env.API_KEY!;

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { question } = req.body;
  if (!question || typeof question !== "string") {
    return res.status(400).json({ error: "Missing question" });
  }

  try {
    const response = await fetch(LAMBDA_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
      },
      body: JSON.stringify({ question }),
    });

    const data = await response.json();
    return res.status(200).json({ answer: data.answer });
  } catch (err) {
    return res.status(500).json({ error: "Failed to reach backend" });
  }
}