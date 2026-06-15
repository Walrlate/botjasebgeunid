import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export const dynamic = 'force-dynamic';

export async function GET() {
  const botApiUrl = process.env.BOT_API_URL;
  
  if (botApiUrl) {
    try {
      // Normalisasi URL
      let fetchUrl = botApiUrl.trim();
      if (!/^https?:\/\//i.test(fetchUrl)) {
        fetchUrl = `https://${fetchUrl}`;
      }
      // Bersihkan trailing slash
      fetchUrl = fetchUrl.replace(/\/+$/, '');
      
      // Pastikan berakhiran /api/prices
      if (!fetchUrl.endsWith('/api/prices')) {
        fetchUrl = `${fetchUrl}/api/prices`;
      }
      
      console.log(`Fetching prices from Bot API: ${fetchUrl}`);
      
      // Fetch dengan timeout 5 detik
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      const response = await fetch(fetchUrl, {
        signal: controller.signal,
        next: { revalidate: 0 } // Jangan dicache
      });
      
      clearTimeout(timeoutId);
      
      if (response.ok) {
        const data = await response.json();
        return NextResponse.json(data);
      } else {
        console.warn(`Failed to fetch from Bot API, status code: ${response.status}. Falling back to local prices.json`);
      }
    } catch (error: any) {
      console.error(`Error fetching from Bot API: ${error.message || error}. Falling back to local prices.json`);
    }
  }

  // Fallback ke file lokal prices.json
  try {
    const filePath = path.join(process.cwd(), 'src', 'prices.json');
    if (fs.existsSync(filePath)) {
      const fileContent = fs.readFileSync(filePath, 'utf8');
      const data = JSON.parse(fileContent);
      return NextResponse.json(data);
    }
    return NextResponse.json({ error: 'Prices file not found' }, { status: 404 });
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
