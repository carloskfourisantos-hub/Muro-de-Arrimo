/* Motor de cálculo: roda o Python (Pyodide) fora da tela principal, para a interface não travar. */
import { loadPyodide } from "./pyodide/pyodide.mjs";

let ponte = null;
const pronto = (async () => {
  const py = await loadPyodide({ indexURL: "pyodide/" });
  postMessage({ tipo: "progresso", texto: "Carregando as bibliotecas de cálculo…" });
  await py.loadPackage(["numpy", "pydantic"]);
  postMessage({ tipo: "progresso", texto: "Carregando o programa…" });
  const zip = await (await fetch("programa.zip")).arrayBuffer();
  py.unpackArchive(zip, "zip", { extractDir: "/programa" });
  py.runPython("import sys; sys.path.insert(0, '/programa')");
  ponte = py.pyimport("ponte");
  return ponte.esquema();
})();

pronto.then(
  (esquema) => postMessage({ tipo: "pronto", esquema }),
  (erro) => postMessage({ tipo: "falha", texto: String(erro) }),
);

onmessage = async (ev) => {
  const { id, funcao, texto } = ev.data;
  try {
    await pronto;
    postMessage({ tipo: "resposta", id, texto: ponte[funcao](texto) });
  } catch (erro) {
    postMessage({ tipo: "resposta", id, erro: String(erro) });
  }
};
