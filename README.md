# VRChatギャラリー

[![Validate generated gallery](https://github.com/KAFKA2306/vrcviewer/actions/workflows/validate.yml/badge.svg)](https://github.com/KAFKA2306/vrcviewer/actions/workflows/validate.yml)

CSVを正準入力として、VRChatのアバターとワールドを検索・カテゴリ閲覧できる静的ギャラリーです。

公開サイト: https://kafka2306.github.io/vrcviewer/

## 正準データと生成物

- `sample_avatars.csv`: アバター入力
- `worlds_*.csv`: ワールド入力。`*` がカテゴリ名になる
- `schema/gallery-csv.schema.json`: CSV行の機械可読契約
- `templates/index.html`: HTMLテンプレート
- `vrcviewer/build.py`: 検証・生成CLI
- `index.html`: **生成物**。手編集しない
- `build-manifest.json`: 実行時に生成する監査manifest。Git管理外で、CIではartifactとして保存する

Notebook (`avatar.ipynb`) は探索・確認用であり、production buildの正準経路ではありません。

## 入力スキーマ

CSVはUTF-8、カンマ区切りで、headerは次の順序に固定します。

```csv
ID,Name,Author ID,Author Name,Thumbnail
```

全列必須です。

- avatar ID: `avtr_<UUID>`
- world ID: `wrld_<UUID>`
- `Author ID`: 空でないsource identifier。既存データには`usr_`形式でないlegacy値があるため、VRChatリンク生成には使用しない
- `Name`, `Author Name`, `Thumbnail`: 空欄禁止
- `Thumbnail`: absolute `https://` URLのみ

同一ファイル内のID重複、複数`worlds_*.csv`間のworld ID重複、完全重複行、不正ID、不正URLは生成前に停止します。カテゴリファイルはファイル名のcase-insensitive順で読み、カテゴリ名はUnicode NFKC正規化・casefold・空白の`-`化を行います。

## Build

Python標準ライブラリだけで実行できます。

```bash
python -m vrcviewer.build
```

このコマンドは全CSVを検証してから、一時ファイルへ完全なHTMLを書き、成功時だけatomic replaceで`index.html`を更新します。検証失敗時は既存の正常な`index.html`を上書きしません。

同じtemplateとCSVから生成される`index.html`はbyte-identicalです。CSV値はHTML本文・属性へ埋め込む前にescapeし、VRChat詳細URLは検証済みresource IDからgeneratorが構築します。

## Validate / CI drift check

```bash
python -m unittest discover -s tests -v
python -m vrcviewer.build --check
```

`--check` はCSV/templateから再生成した内容とtracked `index.html`を比較し、差分があれば失敗します。実行時には`build-manifest.json`も生成され、次を記録します。

- generator version
- build対象commit SHA
- input file一覧とSHA-256
- avatar/world/category別件数
- total unique records
- generated_at
- `index.html` SHA-256

GitHub Actionsでも同じunit testsとdrift checkを実行します。外部VRChat APIへのnetwork accessは検証に不要です。

## データ追加

例:

```csv
ID,Name,Author ID,Author Name,Thumbnail
wrld_a50146fe-4730-4ea2-a4e2-1870751e232b,謎解きワールド Fake,usr_d816b4d3-d092-46b5-963d-df30862d6901,いぬんちゅ,https://api.vrchat.cloud/api/1/image/file_f5a3e796-8534-468e-921a-7865686c0750/6/256
```

新しいカテゴリは`worlds_カテゴリー名.csv`として追加します。変更後は必ず次を実行し、CSVと生成済みHTMLを同じPRへ含めます。

```bash
python -m vrcviewer.build
python -m unittest discover -s tests -v
python -m vrcviewer.build --check
```

公開更新はdefault branchへmergeされた、CIで再生成一致を確認済みの`index.html`を使用します。
