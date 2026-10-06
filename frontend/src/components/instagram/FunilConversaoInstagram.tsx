import { useFunilInstagram } from "@/hooks/useInstagramAnalytics"
import { FunilConversaoChart } from "@/components/dashboard/FunilConversaoChart"

export function FunilConversaoInstagram() {
  const { data, isLoading } = useFunilInstagram()

  return <FunilConversaoChart estagios={data?.estagios} isLoading={isLoading} />
}
