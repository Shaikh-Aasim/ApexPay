async function test() {
  try {
    const res = await fetch("http://localhost:4000/account/balance?vpa=aarav@apex");
    const json = await res.json();
    console.log(JSON.stringify(json, null, 2));
  } catch (e) {
    console.error(e);
  }
}
test();
