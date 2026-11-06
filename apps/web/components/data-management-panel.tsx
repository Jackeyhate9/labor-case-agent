"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArchiveRestore, DatabaseBackup, Trash2 } from "lucide-react";
import { useState } from "react";
import { API_BASE, api, post } from "@/lib/api";
import { Badge, Button, ErrorState } from "./ui";

type DataStatus = {
  database_path: string;
  storage_root: string;
  backup_root: string;
  database_size: number;
  backup_count: number;
  latest_backup?: string | null;
  backup_encryption: string;
};

type BackupResult = {
  filename: string;
  size: number;
  encrypted: boolean;
  api_keys_included: boolean;
};

const formatBytes = (value: number) =>
  new Intl.NumberFormat("zh-CN", {
    style: "unit",
    unit: value >= 1024 ** 3 ? "gigabyte" : "megabyte",
    unitDisplay: "short",
    maximumFractionDigits: 1,
  }).format(value / (value >= 1024 ** 3 ? 1024 ** 3 : 1024 ** 2));

export function DataManagementPanel() {
  const [backupPassphrase, setBackupPassphrase] = useState("");
  const [restorePassphrase, setRestorePassphrase] = useState("");
  const [restoreFile, setRestoreFile] = useState<File>();
  const [restoreConfirmation, setRestoreConfirmation] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const status = useQuery({
    queryKey: ["data-management"],
    queryFn: () => api<DataStatus>("/api/system/data-management"),
  });
  const backup = useMutation({
    mutationFn: () =>
      post("/api/system/backups", { passphrase: backupPassphrase }) as Promise<BackupResult>,
    onSuccess: () => {
      setBackupPassphrase("");
      void status.refetch();
    },
  });
  const restore = useMutation({
    mutationFn: async () => {
      if (!restoreFile) throw new Error("请先选择备份文件");
      const body = new FormData();
      body.append("file", restoreFile);
      body.append("passphrase", restorePassphrase);
      body.append("confirmation", restoreConfirmation);
      return api("/api/system/restore", { method: "POST", body });
    },
    onSuccess: () => {
      setRestorePassphrase("");
      setRestoreConfirmation("");
      setRestoreFile(undefined);
      window.location.reload();
    },
  });
  const clear = useMutation({
    mutationFn: () =>
      post("/api/system/data/clear", { confirmation: deleteConfirmation }),
    onSuccess: () => {
      setDeleteConfirmation("");
      window.location.assign("/");
    },
  });

  return (
    <section className="data-management" aria-labelledby="data-management-title">
      <header>
        <div>
          <p className="section-kicker">DATA CONTROL</p>
          <h2 id="data-management-title">备份、恢复与数据清理</h2>
          <p>备份使用口令加密；API Key 不进入备份，恢复后需要重新填写。</p>
        </div>
        <DatabaseBackup aria-hidden="true" />
      </header>

      {status.isError ? (
        <ErrorState
          message={(status.error as Error).message}
          retry={() => status.refetch()}
        />
      ) : status.data ? (
        <dl className="data-status">
          <div>
            <dt>数据库</dt>
            <dd>{formatBytes(status.data.database_size)}</dd>
          </div>
          <div>
            <dt>加密方式</dt>
            <dd>{status.data.backup_encryption}</dd>
          </div>
          <div>
            <dt>已有备份</dt>
            <dd>{status.data.backup_count} 份</dd>
          </div>
          <div>
            <dt>最近备份</dt>
            <dd>{status.data.latest_backup ?? "尚未创建"}</dd>
          </div>
        </dl>
      ) : null}

      <div className="data-actions-grid">
        <article>
          <DatabaseBackup aria-hidden="true" />
          <h3>创建加密备份</h3>
          <p>包含案件数据库、证据文件和非密钥设置。请妥善保管口令。</p>
          <label>
            备份口令（至少 12 个字符）
            <input
              type="password"
              autoComplete="new-password"
              value={backupPassphrase}
              onChange={(event) => setBackupPassphrase(event.target.value)}
            />
          </label>
          <Button
            busy={backup.isPending}
            disabled={backupPassphrase.length < 12}
            onClick={() => backup.mutate()}
          >
            创建备份
          </Button>
          {backup.data && (
            <a
              className="button button-secondary"
              href={`${API_BASE}/api/system/backups/${encodeURIComponent(backup.data.filename)}`}
              download
            >
              下载 {backup.data.filename}
            </a>
          )}
          {backup.isError && (
            <p className="field-error">{(backup.error as Error).message}</p>
          )}
        </article>

        <article>
          <ArchiveRestore aria-hidden="true" />
          <h3>恢复完整备份</h3>
          <p>恢复会替换当前案件数据。请先为当前数据创建一份新备份。</p>
          <label>
            备份文件
            <input
              type="file"
              accept=".lca-backup"
              onChange={(event) => setRestoreFile(event.target.files?.[0])}
            />
          </label>
          <label>
            备份口令
            <input
              type="password"
              autoComplete="current-password"
              value={restorePassphrase}
              onChange={(event) => setRestorePassphrase(event.target.value)}
            />
          </label>
          <label>
            输入 RESTORE 确认
            <input
              value={restoreConfirmation}
              onChange={(event) => setRestoreConfirmation(event.target.value)}
            />
          </label>
          <Button
            variant="secondary"
            busy={restore.isPending}
            disabled={
              !restoreFile ||
              restorePassphrase.length < 12 ||
              restoreConfirmation !== "RESTORE"
            }
            onClick={() => restore.mutate()}
          >
            校验并恢复
          </Button>
          {restore.isError && (
            <p className="field-error">{(restore.error as Error).message}</p>
          )}
        </article>
      </div>

      <div className="danger-zone">
        <Trash2 aria-hidden="true" />
        <div>
          <h3>清除本机全部案件</h3>
          <p>删除案件数据库记录、证据和派生文件；已下载模型与备份不会删除。</p>
        </div>
        <label>
          输入 DELETE ALL CASES
          <input
            value={deleteConfirmation}
            onChange={(event) => setDeleteConfirmation(event.target.value)}
          />
        </label>
        <Button
          variant="danger"
          busy={clear.isPending}
          disabled={deleteConfirmation !== "DELETE ALL CASES"}
          onClick={() => clear.mutate()}
        >
          永久清除
        </Button>
        {clear.isSuccess && <Badge status="passed">清理完成</Badge>}
        {clear.isError && (
          <p className="field-error">{(clear.error as Error).message}</p>
        )}
      </div>
    </section>
  );
}
