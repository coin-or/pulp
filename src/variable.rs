//! Variable handle (variable stored in a ModelCore). Only created by Model.

use pyo3::prelude::*;
use std::cell::RefCell;
use std::rc::Weak;

use crate::format;
use crate::types::{upgrade_model, Category, ModelCore, VarId};

/// Handle to a variable stored inside a `ModelCore`. Only created by the model.
#[pyclass(unsendable)]
#[derive(Clone)]
pub struct Variable {
    pub id: VarId,
    pub model: Weak<RefCell<ModelCore>>,
}

#[pymethods]
impl Variable {
    pub fn id(&self) -> VarId {
        self.id
    }

    #[getter]
    fn name(&self) -> PyResult<String> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        Ok(core
            .vars
            .get(self.id)
            .map(|v| v.name.clone())
            .unwrap_or_default())
    }

    #[getter]
    fn lb(&self) -> PyResult<f64> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        Ok(core.vars[self.id].lb)
    }

    #[getter]
    fn ub(&self) -> PyResult<f64> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        Ok(core.vars[self.id].ub)
    }

    #[getter]
    fn category(&self) -> PyResult<Category> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        Ok(core.vars[self.id].category)
    }

    #[getter]
    fn value(&self) -> PyResult<Option<f64>> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        Ok(core.vars[self.id].value)
    }

    fn set_value(&self, v: f64) -> PyResult<()> {
        let core_rc = upgrade_model(&self.model)?;
        let mut core = core_rc.borrow_mut();
        if let Some(var) = core.vars.get_mut(self.id) {
            var.value = Some(v);
        }
        Ok(())
    }

    fn set_lb(&self, lb: f64) -> PyResult<()> {
        let core_rc = upgrade_model(&self.model)?;
        let mut core = core_rc.borrow_mut();
        if let Some(var) = core.vars.get_mut(self.id) {
            var.lb = lb;
        }
        Ok(())
    }

    fn set_ub(&self, ub: f64) -> PyResult<()> {
        let core_rc = upgrade_model(&self.model)?;
        let mut core = core_rc.borrow_mut();
        if let Some(var) = core.vars.get_mut(self.id) {
            var.ub = ub;
        }
        Ok(())
    }

    fn set_name(&self, name: String) -> PyResult<()> {
        let core_rc = upgrade_model(&self.model)?;
        let mut core = core_rc.borrow_mut();
        if let Some(var) = core.vars.get_mut(self.id) {
            var.name = name;
        }
        Ok(())
    }

    #[getter]
    fn dj(&self) -> PyResult<Option<f64>> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        Ok(core.vars[self.id].dj)
    }

    fn set_dj(&self, v: f64) -> PyResult<()> {
        let core_rc = upgrade_model(&self.model)?;
        let mut core = core_rc.borrow_mut();
        if let Some(var) = core.vars.get_mut(self.id) {
            var.dj = Some(v);
        }
        Ok(())
    }

    // ── Property checks ──

    fn is_binary(&self) -> PyResult<bool> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        Ok(core.vars[self.id].is_binary())
    }

    fn is_integer(&self) -> PyResult<bool> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        Ok(core.vars[self.id].is_integer())
    }

    fn is_free(&self) -> PyResult<bool> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        Ok(core.vars[self.id].is_free())
    }

    fn is_constant(&self) -> PyResult<bool> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        Ok(core.vars[self.id].is_constant())
    }

    fn is_positive(&self) -> PyResult<bool> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        Ok(core.vars[self.id].is_positive())
    }

    /// CPLEX LP bounds string for this variable.
    fn as_cplex_lp_variable(&self) -> PyResult<String> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        Ok(format::cplex_lp_variable(&core.vars[self.id]))
    }

    /// Validate the variable value against its bounds and integrality.
    #[pyo3(signature = (eps=1e-7))]
    fn valid(&self, eps: f64) -> PyResult<bool> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        let vd = &core.vars[self.id];
        if vd.name == "__dummy" && vd.value.is_none() {
            return Ok(true);
        }
        let val = match vd.value {
            Some(v) => v,
            None => return Ok(false),
        };
        if vd.ub.is_finite() && val > vd.ub + eps {
            return Ok(false);
        }
        if vd.lb.is_finite() && val < vd.lb - eps {
            return Ok(false);
        }
        if vd.category == Category::Integer && (val.round() - val).abs() > eps {
            return Ok(false);
        }
        Ok(true)
    }

    /// Infeasibility gap (distance from feasible region).
    #[pyo3(signature = (mip=true))]
    fn infeasibility_gap(&self, mip: bool) -> PyResult<f64> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        let vd = &core.vars[self.id];
        let val = vd
            .value
            .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("variable value is None"))?;
        if vd.ub.is_finite() && val > vd.ub {
            return Ok(val - vd.ub);
        }
        if vd.lb.is_finite() && val < vd.lb {
            return Ok(val - vd.lb);
        }
        if mip && vd.category == Category::Integer && (val.round() - val) != 0.0 {
            return Ok(val.round() - val);
        }
        Ok(0.0)
    }

    /// Round variable value to bounds and integer if appropriate.
    #[pyo3(signature = (eps_int=1e-5, eps=1e-7))]
    fn round_value(&self, eps_int: f64, eps: f64) -> PyResult<()> {
        let core_rc = upgrade_model(&self.model)?;
        let mut core = core_rc.borrow_mut();
        let vd = &mut core.vars[self.id];
        if let Some(val) = vd.value {
            let mut v = val;
            if vd.ub.is_finite() && v > vd.ub && v <= vd.ub + eps {
                v = vd.ub;
            } else if vd.lb.is_finite() && v < vd.lb && v >= vd.lb - eps {
                v = vd.lb;
            }
            if vd.category == Category::Integer && (v - v.round()).abs() <= eps_int {
                v = v.round();
            }
            vd.value = Some(v);
        }
        Ok(())
    }

    /// Value or default from bounds (used when no solution exists).
    fn value_or_default(&self) -> PyResult<f64> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        let vd = &core.vars[self.id];
        if let Some(v) = vd.value {
            return Ok(v);
        }
        let lb = vd.lb;
        let ub = vd.ub;
        let lb_fin = lb.is_finite();
        let ub_fin = ub.is_finite();
        Ok(if lb_fin && ub_fin {
            if 0.0 >= lb && 0.0 <= ub {
                0.0
            } else if lb >= 0.0 {
                lb
            } else {
                ub
            }
        } else if lb_fin {
            if 0.0 >= lb { 0.0 } else { lb }
        } else if ub_fin {
            if 0.0 <= ub { 0.0 } else { ub }
        } else {
            0.0
        })
    }

    /// Rounded value for integer variables.
    #[pyo3(signature = (eps=1e-5))]
    fn rounded_value(&self, eps: f64) -> PyResult<Option<f64>> {
        let core_rc = upgrade_model(&self.model)?;
        let core = core_rc.borrow();
        let vd = &core.vars[self.id];
        Ok(match vd.value {
            Some(v) if vd.category == Category::Integer && (v - v.round()).abs() <= eps => {
                Some(v.round())
            }
            other => other,
        })
    }
}
