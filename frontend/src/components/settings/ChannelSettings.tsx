import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { getChannels, createChannel, updateChannel, deleteChannel, testChannel } from '../../api/channels'
import type { Platform, Channel } from '../../types'
import styles from './ChannelSettings.module.css'

import type { ReactNode } from 'react'

const VK_OAUTH_URL = 'https://oauth.vk.com/authorize?client_id=2685278&scope=wall,photos,groups,offline&response_type=token&redirect_uri=https://oauth.vk.com/blank.html'

interface FieldDef {
  key: string
  label: string
  placeholder: string
  hint?: ReactNode
}

const PLATFORM_FIELDS: Record<Platform, FieldDef[]> = {
  tg: [
    {
      key: 'bot_token',
      label: 'Bot Token',
      placeholder: '123456:ABC-DEF...',
      hint: (
        <>
          Создай бота через <a href="https://t.me/BotFather" target="_blank" rel="noopener">@BotFather</a> командой <code>/newbot</code> - он пришлёт токен.
        </>
      ),
    },
    {
      key: 'channel',
      label: 'Канал',
      placeholder: '@mychannel или https://t.me/mychannel',
      hint: 'Добавь бота администратором канала (Управление каналом → Администраторы → Добавить → дать право "Публикация сообщений").',
    },
  ],
  vk: [
    {
      key: 'access_token',
      label: 'Access Token',
      placeholder: 'vk1.a.xxx...',
      hint: (
        <>
          <a href={VK_OAUTH_URL} target="_blank" rel="noopener">Открой эту ссылку</a> и подтверди доступ. После этого в адресной строке появится URL вида <code>...#access_token=vk1.a.XXX...&expires_in=0...</code> — скопируй кусок между <code>access_token=</code> и <code>&expires_in</code>. Должен начинаться на <code>vk1.a.</code>
        </>
      ),
    },
    {
      key: 'owner_id',
      label: 'Owner ID (группа со знаком минус)',
      placeholder: '-12345678',
      hint: 'Открой свою группу ВК, нажми на любой пост - в адресной строке будет вида vk.com/wall-12345678_1. Бери число со знаком минус (например -12345678).',
    },
  ],
  ig: [
    { key: 'page_id', label: 'Page ID', placeholder: '12345678' },
    { key: 'access_token', label: 'Access Token', placeholder: 'EAABsb...' },
  ],
  max: [],
  tt: [
    {
      key: 'username',
      label: 'TikTok username',
      placeholder: 'tpabomah_tiktok',
      hint: 'Только для сбора статистики. Публикация в TT не поддерживается - только чтение метрик (просмотры, лайки, комменты, шеры). Указывай username без @ или полную ссылку tiktok.com/@username.',
    },
  ],
}

const STUBS: Platform[] = ['ig', 'max']

export default function ChannelSettings() {
  const qc = useQueryClient()
  const [adding, setAdding] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [newPlatform, setNewPlatform] = useState<Platform>('tg')
  const [newName, setNewName] = useState('')
  const [newConfig, setNewConfig] = useState<Record<string, string>>({})
  const [testingId, setTestingId] = useState<number | null>(null)

  const { data: channels = [] } = useQuery({ queryKey: ['channels'], queryFn: () => getChannels() })

  const createMutation = useMutation({
    mutationFn: () => createChannel({ name: newName, platform: newPlatform, config_json: newConfig }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['channels'] })
      toast.success('Канал добавлен')
      resetForm()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Ошибка при создании'),
  })

  const updateMutation = useMutation({
    mutationFn: (id: number) => updateChannel(id, { name: newName, config_json: newConfig }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['channels'] })
      toast.success('Канал обновлён')
      resetForm()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Ошибка обновления'),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteChannel,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['channels'] }); toast.success('Удалено') },
  })

  function resetForm() {
    setAdding(false)
    setEditingId(null)
    setNewName('')
    setNewConfig({})
  }

  function startEdit(ch: Channel) {
    setAdding(false)
    setEditingId(ch.id)
    setNewPlatform(ch.platform)
    setNewName(ch.name)
    // токены не приходят с бэка (там '***'), оставляем пустыми - значит "не менять"
    const cfg: Record<string, string> = {}
    for (const [k, v] of Object.entries(ch.config_json || {})) {
      if (v !== '***') cfg[k] = String(v)
    }
    setNewConfig(cfg)
  }

  async function handleTest(id: number) {
    setTestingId(id)
    try {
      const r = await testChannel(id)
      toast[r.ok ? 'success' : 'error'](r.message)
    } finally {
      setTestingId(null)
    }
  }

  const fields = PLATFORM_FIELDS[newPlatform] ?? []
  const isEditing = editingId !== null
  const formVisible = adding || isEditing

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <h3>Каналы</h3>
        <button
          className="btn btn-primary btn-sm"
          onClick={() => { if (formVisible) resetForm(); else { setAdding(true); setEditingId(null); setNewName(''); setNewConfig({}) } }}
        >
          {formVisible ? 'Отмена' : '+ Добавить'}
        </button>
      </div>

      {formVisible && (
        <div className={styles.addForm}>
          <div className={styles.formTitle}>
            {isEditing ? `Редактирование канала` : 'Новый канал'}
          </div>
          <select
            className="input"
            value={newPlatform}
            disabled={isEditing}
            onChange={e => { setNewPlatform(e.target.value as Platform); setNewConfig({}) }}
          >
            <option value="tg">Telegram</option>
            <option value="vk">ВКонтакте</option>
            <option value="ig">Instagram</option>
            <option value="max">Max</option>
          </select>
          <input className="input" placeholder="Название канала" value={newName} onChange={e => setNewName(e.target.value)} />
          {STUBS.includes(newPlatform) ? (
            <div className={styles.stub}>
              {newPlatform === 'ig' && 'Instagram требует настройки Meta Business API.'}
              {newPlatform === 'max' && 'Max API не поддерживается автоматически.'}
            </div>
          ) : (
            fields.map(f => {
              const isToken = f.key.includes('token')
              return (
                <div key={f.key} className={styles.fieldGroup}>
                  <input
                    className="input"
                    type={isToken ? 'password' : 'text'}
                    placeholder={isEditing && isToken
                      ? `${f.label}: оставь пустым чтобы не менять`
                      : `${f.label}: ${f.placeholder}`}
                    value={newConfig[f.key] ?? ''}
                    onChange={e => setNewConfig(prev => ({ ...prev, [f.key]: e.target.value }))}
                  />
                  {f.hint && <span className={styles.fieldHint}>{f.hint}</span>}
                </div>
              )
            })
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn btn-primary"
              onClick={() => isEditing ? updateMutation.mutate(editingId!) : createMutation.mutate()}
              disabled={!newName || createMutation.isPending || updateMutation.isPending}
            >
              {isEditing ? 'Сохранить' : 'Добавить'}
            </button>
            <button className="btn btn-secondary" onClick={resetForm}>Отмена</button>
          </div>
        </div>
      )}

      <div className={styles.list}>
        {channels.map(ch => (
          <div key={ch.id} className={styles.item}>
            <span className={`platform-chip chip-${ch.platform}`}>{ch.platform.toUpperCase()}</span>
            <span className={styles.name}>{ch.name}</span>
            <div className={styles.itemActions}>
              <button className="btn btn-secondary btn-sm" onClick={() => handleTest(ch.id)} disabled={testingId === ch.id}>
                {testingId === ch.id ? 'Проверяю...' : 'Тест'}
              </button>
              <button className="btn btn-secondary btn-sm" onClick={() => startEdit(ch)}>Редактировать</button>
              <button className="btn btn-danger btn-sm" onClick={() => deleteMutation.mutate(ch.id)}>Удалить</button>
            </div>
          </div>
        ))}
        {channels.length === 0 && <p className={styles.empty}>Нет каналов - добавьте первый</p>}
      </div>
    </div>
  )
}
