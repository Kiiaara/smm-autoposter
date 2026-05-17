import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useEditorStore } from '../store/editorStore'
import PostEditor from '../components/post-editor/PostEditor'

export default function NewPostPage() {
  const [params] = useSearchParams()

  useEffect(() => {
    // сбрасываем стор при заходе на страницу создания (важно при переходе с EditPostPage)
    const store = useEditorStore.getState()
    store.reset()

    const date = params.get('date')
    const time = params.get('time')
    if (date && time) {
      store.setScheduledAt(`${date}T${time}`)
    }
  }, [params])

  return <PostEditor />
}
