# Agente remoto BBLIA

Companion Android `com.bbl.boxtv.agent` para Android API 24 ou superior. Não substitui a launcher e não inclui chave OpenAI. Faz diagnóstico e recebe pedidos de desinstalação pelo painel ou por uma BBLIA vinculada.

O servidor registra comandos em tabelas próprias. O agente consulta sua fila por HTTPS, coleta os dados e confirma o resultado. A autorização do aparelho e a autorização do controlador são distintas e limitadas ao aparelho. O vínculo do celular usa um código de uso único que expira em dez minutos.

## Integração no painel

Importar `v5_bblia_agent` por último no bootstrap que já carrega `v5`. Fazer backup do bootstrap antes de publicar. A área nova fica em `/admin/agent`, com a autenticação administrativa existente. Cada aparelho oferece o botão de vínculo com a BBLIA do celular.

## Aplicativo

Fontes em `android/`. A configuração privada `files/link.json` é produzida por `v5_bblia_agent.provision(device_id)` em ambiente administrativo; não incorporar essa configuração ao APK nem ao repositório. Usar assinatura persistente para futuras atualizações.

O arquivo de recurso `android/res/raw/isrg_root_x1.pem` deve ser obtido de `https://letsencrypt.org/certs/isrgrootx1.pem` antes da compilação. A configuração TLS aceita as autoridades do sistema e essa raiz pública; não desativa validação de certificado ou hostname.

Neste ambiente o projeto foi compilado com Android SDK 35, build-tools 36, JDK 21 e o compilador Java simples já existente em `Documents/BBLIA-TV-App/bblia_android_build.py`, incluindo `core-lambda-stubs.jar` no bootclasspath do javac. Assinatura, estrutura e alinhamento foram verificados.

## Verificação no aparelho BOX-A0B5CD72

- Instalação do agente: confirmada.
- Recebimento do diagnóstico pela rede Wi-Fi: confirmado; 107 aplicativos encontrados.
- Root acessível pelo ADB: confirmado.
- Root autorizado ao agente: ainda não confirmado; relatório retornou `root=false`.
- Desinstalação remota do aplicativo descartável: pendente da autorização de root.
- Vínculo do celular: interface e ponte publicadas; o teste completo não passou e precisa ser investigado.
- Binários de root, firmware e launcher: não substituídos.

O gerenciador SuperSU solicitou atualização de binário, que foi cancelada. A conexão com o computador deixou de responder antes de concluir o ajuste específico de permissão.

## Limites

Diagnóstico lê somente informações expostas pelo Android: versão, memória, armazenamento, rede, temperatura disponível e aplicativos. Não testa fisicamente fonte, placa ou conectores. A remoção silenciosa exige root autorizado ao próprio agente. Aplicativos do sistema, launcher, guardião de atualização e o agente são protegidos.

Há um diário local antes da execução e uma caixa de saída persistente para reenvio do resultado. Após interrupção de uma desinstalação, o agente confere a presença do pacote e não repete a remoção automaticamente.
