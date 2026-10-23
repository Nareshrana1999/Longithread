export const metadata = { title: "Longithread", description: "Longitudinal care intelligence" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: "system-ui, sans-serif", background: "#070b16", color: "#e7ecff" }}>
        {children}
      </body>
    </html>
  );
}
