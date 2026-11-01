import { mkdirSync } from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
export default function setup() {
  const root = path.resolve(__dirname, "../../..");
  mkdirSync(path.join(root, ".e2e"), { recursive: true });
  execFileSync(
    process.env.ORDERMESH_E2E_PYTHON!,
    ["-m", "alembic", "upgrade", "head"],
    {
      cwd: path.join(root, "services/api"),
      env: {
        ...process.env,
        DATABASE_URL: process.env.ORDERMESH_E2E_DATABASE,
        MIGRATION_DATABASE_URL: process.env.ORDERMESH_E2E_DATABASE,
        APP_ENV: "development",
      },
      stdio: "inherit",
    },
  );
}
